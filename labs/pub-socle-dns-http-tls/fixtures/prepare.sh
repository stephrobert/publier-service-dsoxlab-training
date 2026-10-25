#!/usr/bin/env bash
# Pose le banc d'observation sur edge.lab : une autorité de test, deux noms
# chacun avec son certificat et son application, un routeur TLS qui choisit
# le certificat par SNI et l'application par Host, un résolveur qui connaît
# les deux noms mais pas le troisième, et une configuration de routeur dont
# le repli par défaut laisse un nom inconnu atteindre une application.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-dns-http-tls.log) 2>&1
set -x

WORK=/etc/pub-dht
STATE=/var/lib/pub-dht
CERTS="$WORK/certs"

for u in pub-dht-router pub-dht-boutique pub-dht-compte; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml unbound dnsutils openssl >/dev/null

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
EDGE_IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)

install -d -m 0755 "$WORK" "$CERTS"
install -d -m 0755 /opt/pub-dht
rm -rf "$STATE"
install -d -m 0750 "$STATE"

install -m 0644 /tmp/pub-dht-app.py /opt/pub-dht/app.py
install -m 0644 /tmp/pub-dht-router.py /opt/pub-dht/router.py

# Autorité de test : une CA et un certificat signé par nom, chacun avec le
# bon SAN. Les clés restent en clair : ceci est un banc de lab, pas un
# service réel.
openssl genrsa -out "$CERTS/ca.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days 30 \
  -subj "/CN=Autorite de test pub-socle-dns-http-tls" \
  -out "$CERTS/ca.pem"

for nom in boutique.dht.test compte.dht.test; do
  openssl genrsa -out "$CERTS/$nom.key" 2048 2>/dev/null
  openssl req -new -key "$CERTS/$nom.key" -subj "/CN=$nom" -out "$CERTS/$nom.csr"
  openssl x509 -req -in "$CERTS/$nom.csr" -CA "$CERTS/ca.pem" -CAkey "$CERTS/ca.key" \
    -CAcreateserial -days 30 -sha256 \
    -extfile <(printf 'subjectAltName=DNS:%s' "$nom") \
    -out "$CERTS/$nom.crt"
  rm -f "$CERTS/$nom.csr"
done
chmod 0644 "$CERTS"/*.key "$CERTS"/*.crt "$CERTS/ca.pem"

JETON_BOUTIQUE=$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')
JETON_COMPTE=$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')
NONCE=$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')
NOM_INCONNU="inconnu-$NONCE.dht.test"
PORT_BOUTIQUE=18601
PORT_COMPTE=18602

cat > /etc/systemd/system/pub-dht-boutique.service <<UNIT
[Unit]
Description=Application boutique (lab pub-socle-dns-http-tls)

[Service]
ExecStart=/usr/bin/python3 /opt/pub-dht/app.py boutique $JETON_BOUTIQUE $PORT_BOUTIQUE
Restart=on-failure
UNIT

cat > /etc/systemd/system/pub-dht-compte.service <<UNIT
[Unit]
Description=Application compte (lab pub-socle-dns-http-tls)

[Service]
ExecStart=/usr/bin/python3 /opt/pub-dht/app.py compte $JETON_COMPTE $PORT_COMPTE
Restart=on-failure
UNIT

cat > /etc/systemd/system/pub-dht-router.service <<UNIT
[Unit]
Description=Routeur TLS (lab pub-socle-dns-http-tls)
After=pub-dht-boutique.service pub-dht-compte.service
Requires=pub-dht-boutique.service pub-dht-compte.service

[Service]
ExecStart=/usr/bin/python3 /opt/pub-dht/router.py
Restart=on-failure
AmbientCapabilities=CAP_NET_BIND_SERVICE
UNIT

# Configuration du routeur : l'ordre de déclaration compte, « boutique »
# vient en premier et sert de repli implicite. Le repli est volontairement
# actif : c'est ce qu'un apprenant qui n'a encore rien regardé rencontre.
cat > "$WORK/routes.yaml" <<YAML
noms:
  boutique.dht.test:
    cert: $CERTS/boutique.dht.test.crt
    cle: $CERTS/boutique.dht.test.key
    port_backend: $PORT_BOUTIQUE
  compte.dht.test:
    cert: $CERTS/compte.dht.test.crt
    cle: $CERTS/compte.dht.test.key
    port_backend: $PORT_COMPTE
inconnu:
  action: repli
YAML
chmod 0644 "$WORK/routes.yaml"

# Résolveur : connaît boutique.dht.test et compte.dht.test, et rien d'autre
# dans la zone dht.test (donc NXDOMAIN pour le nom inconnu).
cat > /etc/unbound/unbound.conf.d/pub-dht.conf <<CONF
server:
  interface: $EDGE_IP
  interface: 127.0.0.1
  access-control: 127.0.0.0/8 allow
  access-control: ${EDGE_IP%.*}.0/24 allow
  do-not-query-localhost: no
  local-zone: "dht.test." static
  local-data: "boutique.dht.test. IN A $EDGE_IP"
  local-data: "compte.dht.test. IN A $EDGE_IP"
remote-control:
  control-enable: yes
  control-interface: /run/unbound.ctl
  control-use-cert: no
CONF
rm -f /etc/unbound/unbound.conf.d/remote-control.conf

systemctl daemon-reload
systemctl restart pub-dht-boutique pub-dht-compte
for _ in 1 2 3 4 5; do
  systemctl restart unbound && break
  sleep 2
done
systemctl is-active --quiet unbound
systemctl restart pub-dht-router

for _ in $(seq 1 20); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' --resolve "boutique.dht.test:443:$EDGE_IP" \
    "https://boutique.dht.test/" || true)
  [[ "$code" == 200 ]] && break
  sleep 1
done
[[ "$code" == 200 ]]

for _ in $(seq 1 10); do
  dig +short @"$EDGE_IP" boutique.dht.test A | grep -q . && break
  sleep 1
done

cat > "$STATE/etat.json" <<JSON
{"jeton_boutique": "$JETON_BOUTIQUE", "jeton_compte": "$JETON_COMPTE", "nom_inconnu": "$NOM_INCONNU", "resolveur": "$EDGE_IP", "edge_ip": "$EDGE_IP"}
JSON

cat > /home/student/README-dht <<TXT
Banc d'observation : deux applications publiées en TLS, sur la même adresse
et le même port 443 de edge.lab.

  boutique.dht.test
  compte.dht.test

L'autorité qui a signé les deux certificats est déjà déposée sur poste.lab,
dans /home/student/ca.pem. N'utilisez jamais -k / --insecure : la chaîne doit
se vérifier avec cette autorité.

Le routeur TLS choisit le certificat présenté à partir du SNI de la poignée
de main, puis choisit l'application qui répond à partir de l'en-tête HTTP
Host. Les deux décisions sont indépendantes : rien ne garantit qu'elles
désignent la même application.

Configuration du routeur sur edge.lab : /etc/pub-dht/routes.yaml.

poste.lab interroge le résolveur de edge.lab pour tout nom en dht.test.
Un troisième nom n'a jamais été enregistré dans aucune zone ni déclaré au
routeur.
TXT
chown student:student /home/student/README-dht
