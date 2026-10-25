#!/usr/bin/env bash
# Pose la chaîne de deux proxys et l'application du lab
# pub-socle-reverse-proxy sur edge.lab : un maillon périmètre qui termine
# TLS et décide (mal, au départ) s'il fait confiance à l'origine annoncée
# par le client, un maillon interne qui décide (mal, au départ) s'il fait
# confiance à l'identité déjà portée par la requête, et une application qui
# se contente de rapporter ce qu'elle a reçu. Les maillons interne et
# backend écoutent au départ sur toutes les interfaces : un client peut les
# joindre directement, en contournant le périmètre.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-reverse-proxy.log) 2>&1
set -x

WORK=/opt/pub-rp
ETC=/etc/pub-rp
STATE=/var/lib/pub-rp
CERTS="$ETC/certs"
NOM_TLS=entree.rp.test

for u in pub-rp-perimetre pub-rp-interne pub-rp-backend; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml openssl >/dev/null

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
EDGE_IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)

install -d -m 0755 "$WORK" "$ETC" "$CERTS"
rm -rf "$STATE"
install -d -m 0750 "$STATE"
install -m 0644 /tmp/pub-rp-app.py "$WORK/app.py"

# Autorité de test et certificat du seul maillon qui termine TLS : le
# périmètre. Les clés restent en clair : ceci est un banc de lab.
openssl genrsa -out "$CERTS/ca.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days 30 \
  -subj "/CN=Autorite de test pub-socle-reverse-proxy" \
  -out "$CERTS/ca.pem"
openssl genrsa -out "$CERTS/$NOM_TLS.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/$NOM_TLS.key" -subj "/CN=$NOM_TLS" -out "$CERTS/$NOM_TLS.csr"
openssl x509 -req -in "$CERTS/$NOM_TLS.csr" -CA "$CERTS/ca.pem" -CAkey "$CERTS/ca.key" \
  -CAcreateserial -days 30 -sha256 \
  -extfile <(printf 'subjectAltName=DNS:%s' "$NOM_TLS") \
  -out "$CERTS/$NOM_TLS.crt"
rm -f "$CERTS/$NOM_TLS.csr"
chmod 0644 "$CERTS"/*.key "$CERTS"/*.crt "$CERTS/ca.pem"

mapfile -t PORTS < <(shuf -i 19200-19499 -n 3)
PERIMETRE=${PORTS[0]}
INTERNE=${PORTS[1]}
BACKEND=${PORTS[2]}
SECRET=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
ORIGINE_FORGEE="203.0.113.$((RANDOM % 254 + 1))"

# Politique de confiance : volontairement incomplète au départ. Ni le
# périmètre ni l'interne n'imposent leur propre décision, chacun reconduit
# ce que la requête portait déjà.
cat > "$ETC/politique.yaml" <<YAML
origine:
  forcer_perimetre: false
identite:
  forcer_anonyme: false
YAML
chmod 0644 "$ETC/politique.yaml"

cat > "$ETC/backend.env" <<ENV
ROLE=backend
BIND=0.0.0.0
PORT=$BACKEND
SECRET=$SECRET
ENV
cat > "$ETC/interne.env" <<ENV
ROLE=interne
BIND=0.0.0.0
PORT=$INTERNE
BACKEND_PORT=$BACKEND
POLITIQUE=$ETC/politique.yaml
ENV
cat > "$ETC/perimetre.env" <<ENV
ROLE=perimetre
BIND=0.0.0.0
PORT=$PERIMETRE
INTERNE_PORT=$INTERNE
POLITIQUE=$ETC/politique.yaml
TLS_CERT=$CERTS/$NOM_TLS.crt
TLS_KEY=$CERTS/$NOM_TLS.key
ENV

for role in backend interne perimetre; do
  cat > "/etc/systemd/system/pub-rp-$role.service" <<UNIT
[Unit]
Description=Lab reverse proxy ($role)
After=network.target

[Service]
EnvironmentFile=$ETC/$role.env
ExecStart=/usr/bin/python3 $WORK/app.py
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
UNIT
done

systemctl daemon-reload
for role in backend interne perimetre; do
  systemctl restart "pub-rp-$role.service"
done

for _ in $(seq 1 20); do
  code=$(curl -s --max-time 3 --cacert "$CERTS/ca.pem" \
    --resolve "$NOM_TLS:$PERIMETRE:127.0.0.1" \
    -o /dev/null -w '%{http_code}' "https://$NOM_TLS:$PERIMETRE/" || true)
  [[ "$code" == 200 ]] && break
  sleep 1
done
[[ "$code" == 200 ]]

cat > "$STATE/etat.json" <<JSON
{"perimetre_port": $PERIMETRE, "interne_port": $INTERNE, "backend_port": $BACKEND, "edge_ip": "$EDGE_IP", "nom_tls": "$NOM_TLS", "secret": "$SECRET", "origine_forgee": "$ORIGINE_FORGEE"}
JSON

cat > /home/student/README-rp <<TXT
Chaîne de deux proxys devant une application, sur edge.lab :

  périmètre : https://$NOM_TLS:$PERIMETRE/  (seul maillon censé être joint par un client)
  interne   : http://127.0.0.1:$INTERNE/    (ne devrait jamais être joint directement)
  backend   : http://127.0.0.1:$BACKEND/    (ne devrait jamais être joint directement)

L'autorité qui a signé le certificat du périmètre est déjà déposée sur
poste.lab, dans /home/student/ca.pem. N'utilisez jamais -k / --insecure.

L'application backend répond en JSON avec deux champs : ip_retenue et
identite_retenue, exactement ce qu'elle a reçu dans les en-têtes
X-Forwarded-For et X-User. Elle ne décide rien elle-même.

Politique de confiance, sur edge.lab : $ETC/politique.yaml.
Écoute des trois maillons, sur edge.lab : $ETC/backend.env, $ETC/interne.env,
$ETC/perimetre.env (clé BIND de chacun).
TXT
chown student:student /home/student/README-rp
