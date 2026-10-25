#!/usr/bin/env bash
# Pose le banc de l'épreuve pub-epreuve-socle sur edge.lab : un nom publié
# en TLS (epreuve.test), un backend protégé avec une donnée métier et sa
# sauvegarde, un routeur qui les relie, un résolveur qui connaît le nom.
# Une fois ce banc sain vérifié, UN incident est tiré au sort parmi cinq
# couches possibles et posé par-dessus, sans prévenir lequel.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-epreuve-socle.log) 2>&1
set -x

CONF=/etc/pub-eps
CERTS="$CONF/certs"
STATE=/var/lib/pub-eps
BACKUP=/var/backups/pub-eps
NOM=epreuve.test
BACKEND_PORT=18820

for u in pub-eps-router pub-eps-backend; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml unbound dnsutils openssl >/dev/null

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
EDGE_IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)

install -d -m 0755 "$CONF" "$CERTS"
install -d -m 0755 /opt/pub-eps
rm -rf "$STATE" "$BACKUP"
install -d -m 0755 "$STATE" "$BACKUP"

install -m 0644 /tmp/pub-eps-app.py /opt/pub-eps/app.py
install -m 0644 /tmp/pub-eps-router.py /opt/pub-eps/router.py

# Autorité de test et certificat du nom publié.
openssl genrsa -out "$CERTS/ca.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days 30 \
  -subj "/CN=Autorite de test pub-epreuve-socle" \
  -out "$CERTS/ca.pem"
openssl genrsa -out "$CERTS/$NOM.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/$NOM.key" -subj "/CN=$NOM" -out "$CERTS/$NOM.csr"
openssl x509 -req -in "$CERTS/$NOM.csr" -CA "$CERTS/ca.pem" -CAkey "$CERTS/ca.key" \
  -CAcreateserial -days 30 -sha256 \
  -extfile <(printf 'subjectAltName=DNS:%s' "$NOM") \
  -out "$CERTS/$NOM.crt"
rm -f "$CERTS/$NOM.csr"

# Un second certificat, auto-signé, qui ne descend d'aucune autorité connue
# du client : sert un incident possible sur la couche TLS.
openssl genrsa -out "$CERTS/intrus.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/intrus.key" -sha256 -days 30 \
  -subj "/CN=$NOM" \
  -extensions v3_req \
  -config <(cat <<CNF
[req]
distinguished_name=req
[v3_req]
subjectAltName=DNS:$NOM
CNF
) \
  -out "$CERTS/intrus.crt"
chmod 0644 "$CERTS"/*.key "$CERTS"/*.crt "$CERTS/ca.pem"

cat > /etc/systemd/system/pub-eps-backend.service <<UNIT
[Unit]
Description=Backend protege (epreuve pub-epreuve-socle)

[Service]
Environment=PORT=$BACKEND_PORT DONNEES=$STATE/donnees.json
ExecStart=/usr/bin/python3 /opt/pub-eps/app.py
Restart=on-failure
UNIT

cat > /etc/systemd/system/pub-eps-router.service <<UNIT
[Unit]
Description=Routeur TLS (epreuve pub-epreuve-socle)
After=pub-eps-backend.service
Requires=pub-eps-backend.service

[Service]
Environment=BIND=0.0.0.0 PORT=443 CERT=$CERTS/$NOM.crt CLE=$CERTS/$NOM.key
ExecStart=/usr/bin/python3 /opt/pub-eps/router.py
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
UNIT

VALEUR=$(( (RANDOM % 900) + 100 ))
cat > "$STATE/donnees.json" <<JSON
{"valeur": $VALEUR}
JSON
chmod 0644 "$STATE/donnees.json"

cat > "$CONF/route.yaml" <<YAML
port_backend: $BACKEND_PORT
YAML
chmod 0644 "$CONF/route.yaml"

# Sauvegarde : prise ici, avant tout incident. Sa fiabilite n'est pas
# encore prouvee tant que personne n'a ecrit ni joue de procedure de
# restauration a partir d'elle.
cp "$CONF/route.yaml" "$BACKUP/route.yaml.bak"
cp "$STATE/donnees.json" "$BACKUP/donnees.json.bak"
chmod 0644 "$BACKUP"/*.bak

cat > /etc/unbound/unbound.conf.d/pub-eps.conf <<CONF
server:
  interface: $EDGE_IP
  interface: 127.0.0.1
  access-control: 127.0.0.0/8 allow
  access-control: ${EDGE_IP%.*}.0/24 allow
  do-not-query-localhost: no
  local-zone: "test." static
  local-data: "$NOM. IN A $EDGE_IP"
remote-control:
  control-enable: yes
  control-interface: /run/unbound.ctl
  control-use-cert: no
CONF
rm -f /etc/unbound/unbound.conf.d/remote-control.conf

install -d -m 0755 "$STATE"
cat > "$STATE/etat.json" <<JSON
{"edge_ip": "$EDGE_IP", "nom": "$NOM", "backend_port": $BACKEND_PORT}
JSON
chmod 0644 "$STATE/etat.json"

systemctl daemon-reload
systemctl restart pub-eps-backend
for _ in 1 2 3 4 5; do
  systemctl restart unbound && break
  sleep 2
done
systemctl is-active --quiet unbound
systemctl restart pub-eps-router

# Preuve que le banc est sain AVANT tout incident : si ceci echoue, le lab
# lui-meme est casse, pas l'incident pedagogique.
for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --cacert "$CERTS/ca.pem" \
    --resolve "$NOM:443:127.0.0.1" "https://$NOM/" || true)
  [[ "$code" == 200 ]] && break
  sleep 1
done
[[ "$code" == 200 ]]

# --- Tirage et pose d'un seul incident parmi cinq couches, sans annonce --
declare -A JETONS=(
  [dns]="la zone unbound de $NOM est absente (resolution en NXDOMAIN)"
  [transport]="pub-eps-router.service est lie a 127.0.0.1 au lieu de 0.0.0.0"
  [tls]="le certificat servi par pub-eps-router.service n'est pas signe par l'autorite de test"
  [route]="port_backend est errone dans $CONF/route.yaml"
  [backend]="l'unite pub-eps-backend.service est arretee"
)
# Mots-clés courts, distincts entre eux, utilisés par le test automatisé
# pour vérifier la couche nommée sans se contenter d'un simple repérage de
# mot isolé : chaque phrase est propre à une seule couche.
declare -A MOTSCLES=(
  [dns]="nxdomain"
  [transport]="127.0.0.1 au lieu de 0.0.0.0"
  [tls]="non signe par"
  [route]="port_backend errone"
  [backend]="backend.service arretee"
)
INCIDENT=$(shuf -e dns transport tls route backend -n 1)

case "$INCIDENT" in
  dns)
    cat > /etc/unbound/unbound.conf.d/pub-eps.conf <<CONF
server:
  interface: $EDGE_IP
  interface: 127.0.0.1
  access-control: 127.0.0.0/8 allow
  access-control: ${EDGE_IP%.*}.0/24 allow
  do-not-query-localhost: no
  local-zone: "test." static
remote-control:
  control-enable: yes
  control-interface: /run/unbound.ctl
  control-use-cert: no
CONF
    systemctl restart unbound
    ;;
  transport)
    sed -i 's/^Environment=BIND=0.0.0.0/Environment=BIND=127.0.0.1/' \
      /etc/systemd/system/pub-eps-router.service
    systemctl daemon-reload
    systemctl restart pub-eps-router
    ;;
  tls)
    sed -i "s#CERT=$CERTS/$NOM.crt CLE=$CERTS/$NOM.key#CERT=$CERTS/intrus.crt CLE=$CERTS/intrus.key#" \
      /etc/systemd/system/pub-eps-router.service
    systemctl daemon-reload
    systemctl restart pub-eps-router
    ;;
  route)
    cat > "$CONF/route.yaml" <<YAML
port_backend: $((BACKEND_PORT + 1))
YAML
    ;;
  backend)
    systemctl stop pub-eps-backend
    ;;
esac

AUTRES=""
MOTSCLES_AUTRES=""
for cle in "${!JETONS[@]}"; do
  if [[ "$cle" != "$INCIDENT" ]]; then
    AUTRES="${AUTRES}  - \"${JETONS[$cle]}\"
"
    MOTSCLES_AUTRES="${MOTSCLES_AUTRES}  - \"${MOTSCLES[$cle]}\"
"
  fi
done

install -d -m 0700 /root
cat > /root/.pub-eps-secret.yaml <<YAML
incident: $INCIDENT
token_correct: "${JETONS[$INCIDENT]}"
mot_cle: "${MOTSCLES[$INCIDENT]}"
tokens_autres:
$AUTRES
mots_cle_autres:
$MOTSCLES_AUTRES
YAML
chmod 0600 /root/.pub-eps-secret.yaml

cat > /home/student/README-epreuve <<TXT
Publication observee : https://$NOM/ sur edge.lab (443). L'autorite qui a
signe le certificat est deposee sur poste.lab, dans /home/student/ca.pem.
Ne jamais utiliser -k / --insecure.

Ce service tournait deja avant que vous n'y touchiez. Un incident, non
annonce, a ete pose dessus apres coup.

Livrables attendus, sur edge.lab :
- /home/student/dossier.md : le dossier d'architecture (noms, flux,
  identites et responsabilites) de ce service tel qu'il est publie.
- /home/student/incident.yaml : la couche et le composant reellement
  fautifs, et votre explication appuyee sur ce que vous avez observe.
  Format :
    couche: route    # un parmi : dns, transport, tls, route, backend
    composant: "..."
    explication: "..."
- /home/student/restaurer.sh : un script qui restaure
  /etc/pub-eps/route.yaml et /var/lib/pub-eps/donnees.json depuis
  /var/backups/pub-eps/ et fait repondre au routeur la vraie valeur.
TXT
chown student:student /home/student/README-epreuve
