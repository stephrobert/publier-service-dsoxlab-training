#!/usr/bin/env bash
# Pose le banc du lab pub-socle-depannage sur edge.lab : un nom publié en
# TLS (depan.test), un backend protégé (route /admin toujours refusée), un
# routeur qui les relie, un résolveur qui connaît le nom, et un bruit de
# fond sans rapport avec la panne. Une fois ce banc sain vérifié, UNE seule
# panne est tirée au sort parmi cinq couches et appliquée par-dessus.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-depannage.log) 2>&1
set -x

CONF=/etc/pub-dep
CERTS="$CONF/certs"
NOM=depan.test
BACKEND_PORT=18810

for u in pub-dep-router pub-dep-backend pub-dep-bruit; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml unbound dnsutils openssl >/dev/null

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
EDGE_IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)

install -d -m 0755 "$CONF" "$CERTS"
install -d -m 0755 /opt/pub-dep

install -m 0644 /tmp/pub-dep-app.py /opt/pub-dep/app.py
install -m 0644 /tmp/pub-dep-router.py /opt/pub-dep/router.py

# Autorité de test et certificat du nom publié.
openssl genrsa -out "$CERTS/ca.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days 30 \
  -subj "/CN=Autorite de test pub-socle-depannage" \
  -out "$CERTS/ca.pem"
openssl genrsa -out "$CERTS/$NOM.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/$NOM.key" -subj "/CN=$NOM" -out "$CERTS/$NOM.csr"
openssl x509 -req -in "$CERTS/$NOM.csr" -CA "$CERTS/ca.pem" -CAkey "$CERTS/ca.key" \
  -CAcreateserial -days 30 -sha256 \
  -extfile <(printf 'subjectAltName=DNS:%s' "$NOM") \
  -out "$CERTS/$NOM.crt"
rm -f "$CERTS/$NOM.csr"

# Un second certificat, auto-signé, qui ne descend d'aucune autorité connue
# du client : sert la panne « tls ». Jamais utilisé tant que la panne tls
# n'est pas tirée.
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

cat > /etc/systemd/system/pub-dep-backend.service <<UNIT
[Unit]
Description=Backend protege (lab pub-socle-depannage)

[Service]
Environment=PORT=$BACKEND_PORT
ExecStart=/usr/bin/python3 /opt/pub-dep/app.py
Restart=on-failure
UNIT

cat > /etc/systemd/system/pub-dep-router.service <<UNIT
[Unit]
Description=Routeur TLS (lab pub-socle-depannage)
After=pub-dep-backend.service
Requires=pub-dep-backend.service

[Service]
Environment=BIND=0.0.0.0 PORT=443 CERT=$CERTS/$NOM.crt CLE=$CERTS/$NOM.key
ExecStart=/usr/bin/python3 /opt/pub-dep/router.py
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
UNIT

# Bruit de fond : un avertissement plausible, sans rapport avec aucune des
# cinq pannes possibles. Il ne casse rien ; il encombre juste le journal
# pour que l'hypothèse ne se formule pas sur la seule lecture d'un message
# qui fait peur.
cat > /etc/systemd/system/pub-dep-bruit.service <<'UNIT'
[Unit]
Description=Bruit de fond sans rapport avec la panne (lab pub-socle-depannage)

[Service]
ExecStart=/bin/bash -c 'while true; do echo "WARN cache de session pub-dep a 92%% (purge conseillee)"; sleep 7; done'
Restart=on-failure
UNIT

cat > "$CONF/route.yaml" <<YAML
port_backend: $BACKEND_PORT
YAML
chmod 0644 "$CONF/route.yaml"

cat > /etc/unbound/unbound.conf.d/pub-dep.conf <<CONF
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

install -d -m 0755 /var/lib/pub-dep
cat > /var/lib/pub-dep/etat.json <<JSON
{"edge_ip": "$EDGE_IP", "nom": "$NOM", "backend_port": $BACKEND_PORT}
JSON
chmod 0644 /var/lib/pub-dep/etat.json

systemctl daemon-reload
systemctl restart pub-dep-backend
for _ in 1 2 3 4 5; do
  systemctl restart unbound && break
  sleep 2
done
systemctl is-active --quiet unbound
systemctl restart pub-dep-router
systemctl restart pub-dep-bruit

# Preuve que le banc est sain AVANT toute panne : si ceci échoue, le lab lui
# même est cassé, pas la panne pédagogique.
for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --cacert "$CERTS/ca.pem" \
    --resolve "$NOM:443:127.0.0.1" "https://$NOM/" || true)
  [[ "$code" == 200 ]] && break
  sleep 1
done
[[ "$code" == 200 ]]

# --- Tirage et pose d'une seule panne parmi cinq couches -------------------
declare -A JETONS=(
  [dns]="la zone unbound de $NOM est absente (resolution en NXDOMAIN)"
  [transport]="pub-dep-router.service est lie a 127.0.0.1 au lieu de 0.0.0.0"
  [tls]="le certificat servi par pub-dep-router.service n'est pas signe par l'autorite de test"
  [route]="port_backend est errone dans $CONF/route.yaml"
  [backend]="l'unite pub-dep-backend.service est arretee"
)
# Mots-clés courts, distincts entre eux, utilisés par le test automatisé
# pour vérifier le composant nommé sans se contenter d'un simple repérage
# de mot isolé : chaque phrase est propre à une seule couche.
declare -A MOTSCLES=(
  [dns]="nxdomain"
  [transport]="127.0.0.1 au lieu de 0.0.0.0"
  [tls]="non signe par"
  [route]="port_backend errone"
  [backend]="backend.service arretee"
)
PANNE=$(shuf -e dns transport tls route backend -n 1)

case "$PANNE" in
  dns)
    cat > /etc/unbound/unbound.conf.d/pub-dep.conf <<CONF
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
      /etc/systemd/system/pub-dep-router.service
    systemctl daemon-reload
    systemctl restart pub-dep-router
    ;;
  tls)
    sed -i "s#CERT=$CERTS/$NOM.crt CLE=$CERTS/$NOM.key#CERT=$CERTS/intrus.crt CLE=$CERTS/intrus.key#" \
      /etc/systemd/system/pub-dep-router.service
    systemctl daemon-reload
    systemctl restart pub-dep-router
    ;;
  route)
    cat > "$CONF/route.yaml" <<YAML
port_backend: $((BACKEND_PORT + 1))
YAML
    ;;
  backend)
    systemctl stop pub-dep-backend
    ;;
esac

AUTRES=""
MOTSCLES_AUTRES=""
for cle in "${!JETONS[@]}"; do
  if [[ "$cle" != "$PANNE" ]]; then
    AUTRES="${AUTRES}  - \"${JETONS[$cle]}\"
"
    MOTSCLES_AUTRES="${MOTSCLES_AUTRES}  - \"${MOTSCLES[$cle]}\"
"
  fi
done

install -d -m 0700 /root
cat > /root/.pub-dep-secret.yaml <<YAML
fault: $PANNE
token_correct: "${JETONS[$PANNE]}"
mot_cle: "${MOTSCLES[$PANNE]}"
tokens_autres:
$AUTRES
mots_cle_autres:
$MOTSCLES_AUTRES
YAML
chmod 0600 /root/.pub-dep-secret.yaml

cat > /home/student/README-depannage <<TXT
Publication observee : https://$NOM/ sur edge.lab (443). L'autorite qui a
signe le certificat est deposee sur poste.lab, dans /home/student/ca.pem.
Ne jamais utiliser -k / --insecure.

Une panne a ete tiree au sort parmi cinq couches possibles (DNS, transport,
TLS, route, backend) et posee sur ce banc, par ailleurs sain. Un bruit de
fond sans rapport avec cette panne tourne aussi : le journal peut contenir
des avertissements qui ne mènent nulle part.

Livrables attendus, sur edge.lab :
- /home/student/journal.md : vos observations horodatees, l'hypothese que
  vous formulez, le test cible qui la confirme ou la refute.
- /home/student/diagnostic.yaml : la couche fautive (dns, transport, tls,
  route ou backend) et le composant precis, identifie sur ce banc.

Corrigez ensuite la panne sur place, puis repassez votre propre matrice de
recette (DNS, TLS, route metier, route interne, acces direct au backend)
pour prouver qu'aucune protection n'a ete retiree au passage.
TXT
chown student:student /home/student/README-depannage
