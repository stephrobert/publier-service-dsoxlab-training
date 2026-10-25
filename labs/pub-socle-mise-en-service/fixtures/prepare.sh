#!/usr/bin/env bash
# Pose le banc du lab pub-socle-mise-en-service sur edge.lab : une autorité
# de test, un nom publié en TLS, deux origines (une active, une candidate
# invalide), un routeur qui les sert selon /etc/pub-mes/route.yaml, un état
# métier (stock) et sa sauvegarde, et un résolveur qui connaît le nom.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-mise-en-service.log) 2>&1
set -x

CONF=/etc/pub-mes
CERTS="$CONF/certs"
STATE=/var/lib/pub-mes
BACKUP=/var/backups/pub-mes
NOM=service.mes.test

for u in pub-mes-router pub-mes-origine-a pub-mes-origine-b; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml unbound dnsutils openssl >/dev/null

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
EDGE_IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)

install -d -m 0755 "$CONF" "$CERTS"
install -d -m 0755 /opt/pub-mes
rm -rf "$STATE" "$BACKUP"
install -d -m 0755 "$STATE" "$BACKUP"

install -m 0644 /tmp/pub-mes-app.py /opt/pub-mes/app.py
install -m 0644 /tmp/pub-mes-router.py /opt/pub-mes/router.py

# Autorité de test et certificat du seul nom publié.
openssl genrsa -out "$CERTS/ca.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days 30 \
  -subj "/CN=Autorite de test pub-socle-mise-en-service" \
  -out "$CERTS/ca.pem"
openssl genrsa -out "$CERTS/$NOM.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/$NOM.key" -subj "/CN=$NOM" -out "$CERTS/$NOM.csr"
openssl x509 -req -in "$CERTS/$NOM.csr" -CA "$CERTS/ca.pem" -CAkey "$CERTS/ca.key" \
  -CAcreateserial -days 30 -sha256 \
  -extfile <(printf 'subjectAltName=DNS:%s' "$NOM") \
  -out "$CERTS/$NOM.crt"
rm -f "$CERTS/$NOM.csr"
chmod 0644 "$CERTS"/*.key "$CERTS"/*.crt "$CERTS/ca.pem"

PORT_A=18701
PORT_B=18702
STOCK=$(( (RANDOM % 900) + 100 ))

cat > /etc/systemd/system/pub-mes-origine-a.service <<UNIT
[Unit]
Description=Origine active a (lab pub-socle-mise-en-service)

[Service]
Environment=ORIGIN_ID=a PORT=$PORT_A STOCK=$STATE/stock.json
ExecStart=/usr/bin/python3 /opt/pub-mes/app.py
Restart=on-failure
UNIT

cat > /etc/systemd/system/pub-mes-origine-b.service <<UNIT
[Unit]
Description=Origine candidate invalide b (lab pub-socle-mise-en-service)

[Service]
Environment=ORIGIN_ID=b PORT=$PORT_B STOCK=$STATE/stock.json
ExecStart=/usr/bin/python3 /opt/pub-mes/app.py
Restart=on-failure
UNIT

cat > /etc/systemd/system/pub-mes-router.service <<UNIT
[Unit]
Description=Routeur TLS (lab pub-socle-mise-en-service)
After=pub-mes-origine-a.service pub-mes-origine-b.service
Requires=pub-mes-origine-a.service pub-mes-origine-b.service

[Service]
ExecStart=/usr/bin/python3 /opt/pub-mes/router.py
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
UNIT

# Etat metier initial : un stock de reference.
cat > "$STATE/stock.json" <<JSON
{"stock": $STOCK}
JSON
chmod 0644 "$STATE/stock.json"

# Configuration active : la recette porte un bogue a corriger
# (expose_interne doit passer a false), le reste est deja juste.
cat > "$CONF/route.yaml" <<YAML
origine_active: a
ttl_cache_s: 24
expose_interne: true
port_a: $PORT_A
port_b: $PORT_B
YAML
chmod 0644 "$CONF/route.yaml"

# Sauvegarde : une copie prise ici, avant toute panne. Sa fiabilite n'est pas
# encore prouvee : personne n'a encore ecrit ni joue de procedure de
# restauration a partir d'elle.
cp "$CONF/route.yaml" "$BACKUP/route.yaml.bak"
cp "$STATE/stock.json" "$BACKUP/stock.json.bak"
chmod 0644 "$BACKUP"/*.bak

# Resolveur : connait service.mes.test, et rien d'autre dans sa zone.
cat > /etc/unbound/unbound.conf.d/pub-mes.conf <<CONF
server:
  interface: $EDGE_IP
  interface: 127.0.0.1
  access-control: 127.0.0.0/8 allow
  access-control: ${EDGE_IP%.*}.0/24 allow
  do-not-query-localhost: no
  local-zone: "mes.test." static
  local-data: "$NOM. IN A $EDGE_IP"
remote-control:
  control-enable: yes
  control-interface: /run/unbound.ctl
  control-use-cert: no
CONF
rm -f /etc/unbound/unbound.conf.d/remote-control.conf

systemctl daemon-reload
systemctl restart pub-mes-origine-a pub-mes-origine-b
for _ in 1 2 3 4 5; do
  systemctl restart unbound && break
  sleep 2
done
systemctl is-active --quiet unbound
systemctl restart pub-mes-router

for _ in $(seq 1 20); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$NOM:443:$EDGE_IP" \
    "https://$NOM/catalogue" || true)
  [[ "$code" == 200 ]] && break
  sleep 1
done
[[ "$code" == 200 ]]

cat > "$STATE/etat.json" <<JSON
{"stock_initial": $STOCK, "edge_ip": "$EDGE_IP", "nom": "$NOM"}
JSON

cat > /home/student/README-mes <<TXT
Publication observee : https://$NOM/ sur edge.lab (443).

L'autorite qui a signe le certificat est deposee sur poste.lab, dans
/home/student/ca.pem. Ne jamais utiliser -k / --insecure.

Configuration active du routeur : /etc/pub-mes/route.yaml (ports des deux
origines, origine active, duree de cache et exposition de la route
interne).

Etat metier : /var/lib/pub-mes/stock.json. Sa sauvegarde est deja la,
dans /var/backups/pub-mes/, mais personne ne l'a encore essayee.
TXT
chown student:student /home/student/README-mes
