#!/usr/bin/env bash
# Pose la situation : une autorite ACME locale en marche, un client ACME
# disponible, deux noms a servir, et AUCUN certificat.
#
# POURQUOI UNE AUTORITE LOCALE ET NON UN VRAI LET'S ENCRYPT
#
# Parce qu'un lab ne doit dependre ni d'Internet ni d'un quota. Pebble parle
# le meme protocole, delivre de vrais certificats, et son autorite racine
# change a CHAQUE demarrage : c'est voulu par ses auteurs, et cela oblige a
# recuperer la racine au lieu de la supposer.
#
# CE QUE LE SETUP NE FAIT PAS : il n'obtient aucun certificat, ne configure
# aucun bloc HTTPS, ne pose aucun mecanisme de renouvellement.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-tls.log) 2>&1
set -x

WORK=/opt/pub-nginx-tls

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl ca-certificates

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/lego" "$WORK/defi"

docker rm -f pub-nginx-tls-pebble pub-nginx-tls-challtestsrv 2>/dev/null || true
for img in "$IMG_PEBBLE" "$IMG_CHALLTESTSRV" "$IMG_LEGO"; do
  docker pull "$img"
done

# Pebble valide le defi HTTP-01 en allant frapper le port 80 de la machine.
# On le lui dit explicitement : par defaut il viserait le port 5002.
cat > "$WORK/pebble.json" <<'JSON'
{
  "pebble": {
    "listenAddress": "0.0.0.0:14000",
    "managementListenAddress": "0.0.0.0:15000",
    "certificate": "test/certs/localhost/cert.pem",
    "privateKey": "test/certs/localhost/key.pem",
    "httpPort": 80,
    "tlsPort": 443,
    "ocspResponderURL": "",
    "externalAccountBindingRequired": false
  }
}
JSON

cat > "$WORK/compose.yaml" <<YAML
services:
  pebble:
    image: "$IMG_PEBBLE"
    container_name: pub-nginx-tls-pebble
    network_mode: host
    restart: unless-stopped
    environment:
      # Pebble refuse par defaut une validation sur deux, pour obliger les
      # clients a retenter. Dans un lab, cela rend le resultat aleatoire et
      # le diagnostic impossible : on le desactive.
      PEBBLE_VA_NOSLEEP: "1"
      PEBBLE_WFE_NONCEREJECT: "0"
    volumes:
      - ./pebble.json:/test/config/pebble-config.json:ro
    command: ["-config", "/test/config/pebble-config.json", "-dnsserver", "127.0.0.1:8053"]
  challtestsrv:
    image: "$IMG_CHALLTESTSRV"
    container_name: pub-nginx-tls-challtestsrv
    network_mode: host
    restart: unless-stopped
    command: ["-dns01", ":8053", "-http01", "", "-https01", "", "-tlsalpn01", "", "-management", ":8055"]
YAML
chown -R student:docker "$WORK"

docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

# Les deux noms resolvent vers la machine, pour le client comme pour Pebble.
for nom in app.lab.test api.lab.test; do
  grep -q " $nom\$" /etc/hosts || echo "127.0.0.1 $nom" >> /etc/hosts
done
curl -s -X POST -d '{"host":"app.lab.test","addresses":["127.0.0.1"]}' \
  http://127.0.0.1:8055/add-a || true
curl -s -X POST -d '{"host":"api.lab.test","addresses":["127.0.0.1"]}' \
  http://127.0.0.1:8055/add-a || true

# Le backend a publier.
cat > "$WORK/application.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Application(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        corps = f"nginx-tls backend: {self.headers.get('Host', '')}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18097), Application).serve_forever()
PY
chmod 0644 "$WORK/application.py"

cat > /etc/systemd/system/pub-nginx-tls-backend.service <<'UNIT'
[Unit]
Description=Backend for the Nginx TLS lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-tls/application.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-tls-backend.service

# La configuration de depart : HTTP seulement, et le chemin du defi servi en
# clair depuis un repertoire que le client ACME remplira.
cat > /etc/nginx/conf.d/tls.conf <<'CONF'
server {
    listen 80 default_server;
    server_name app.lab.test api.lab.test;

    # Le defi HTTP-01 se sert EN CLAIR : une redirection vers HTTPS posee
    # ici empecherait l'autorite de valider, et le certificat ne serait
    # jamais emis.
    location /.well-known/acme-challenge/ {
        root /opt/pub-nginx-tls/defi;
    }

    location / {
        proxy_pass http://127.0.0.1:18097;
        proxy_set_header Host $host;
    }
}
CONF

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Le banc TLS.

  autorite ACME locale : https://localhost:14000/dir
  gestion de Pebble    : https://localhost:15000
  racine de l'autorite : https://localhost:15000/roots/0
  client ACME          : l'image $IMG_LEGO, deja tiree
  noms a servir        : app.lab.test et api.lab.test
  repertoire du defi   : /opt/pub-nginx-tls/defi (deja servi en clair par
                         Nginx sous /.well-known/acme-challenge/)

L'AUTORITE RACINE DE PEBBLE CHANGE A CHAQUE DEMARRAGE. C'est voulu par ses
auteurs : elle se recupere sur /roots/0, jamais ne se suppose.

CE QUE LA VALIDATION APPELLERA

Elle a besoin de declencher un renouvellement sans connaitre le mecanisme
que vous aurez choisi. Fournissez donc un point d'entree :

    /usr/local/bin/renouveler-certificats

Executable, il doit obtenir une nouvelle serie et la faire servir, sans
redemarrer le processus Nginx et sans effacer le compte ACME.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 60); do
  if curl --max-time 3 --silent --output /dev/null -k https://127.0.0.1:14000/dir \
     && curl --max-time 3 --silent --output /dev/null http://127.0.0.1/; then
    echo "Situation posée : autorité locale en marche, aucun certificat."
    exit 0
  fi
  sleep 2
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Pebble ou Nginx ne répond pas." >&2
exit 1
