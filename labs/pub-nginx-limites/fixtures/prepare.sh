#!/usr/bin/env bash
# Pose la situation : une API limitee, mal.
#
# LES TROIS DEFAUTS POSES
#   1. `set_real_ip_from 0.0.0.0/0` : Nginx croit le X-Forwarded-For de
#      N'IMPORTE QUEL appelant. Forger une adresse differente a chaque
#      requete suffit alors a echapper a toute limite par IP.
#   2. une SEULE zone partagee entre /api et /admin : marteler
#      l'administration epuise la part de la route publique.
#   3. des valeurs inadaptees : 1 requete par minute, ce qui refuse le
#      trafic legitime, et aucune limite de corps.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-limites.log) 2>&1
set -x

WORK=/opt/pub-nginx-limites

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

cat > "$WORK/api.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Api(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _repondre(self):
        cle = self.headers.get("X-Cle-Api", "aucune")
        corps = (
            f"api chemin={self.path} cle={cle} "
            f"vu={self.headers.get('X-Forwarded-For', 'direct')}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    do_GET = _repondre

    def do_POST(self):
        taille = int(self.headers.get("Content-Length", "0") or 0)
        self.rfile.read(taille)
        self._repondre()

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18098), Api).serve_forever()
PY
chmod 0644 "$WORK/api.py"

cat > /etc/systemd/system/pub-nginx-limites-api.service <<'UNIT'
[Unit]
Description=API for the Nginx limits lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-limites/api.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-limites-api.service

cat > /etc/nginx/conf.d/limites.conf <<'CONF'
# UNE SEULE zone, partagee par toutes les routes : la penalite de
# l'administration retombe sur le public.
limit_req_zone $binary_remote_addr zone=globale:10m rate=1r/m;

server {
    listen 80 default_server;
    server_name api.lab.test;

    # Nginx croit le X-Forwarded-For de n'importe qui : forger une adresse
    # differente a chaque requete suffit a echapper a la limite.
    set_real_ip_from 0.0.0.0/0;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;

    location /public {
        limit_req zone=globale;
        proxy_pass http://127.0.0.1:18098;
        proxy_set_header Host $host;
        proxy_set_header X-Cle-Api $http_x_cle_api;
    }

    location /admin {
        limit_req zone=globale;
        proxy_pass http://127.0.0.1:18098;
        proxy_set_header Host $host;
        proxy_set_header X-Cle-Api $http_x_cle_api;
    }

    location / {
        proxy_pass http://127.0.0.1:18098;
        proxy_set_header Host $host;
        proxy_set_header X-Cle-Api $http_x_cle_api;
    }
}
CONF

cat > "$WORK/politique.txt" <<'TXT'
La politique a appliquer.

  Le proxy amont de confiance du lab est 127.0.0.1, et LUI SEUL. Tout autre
  appelant est direct, et ce qu'il raconte de lui-meme ne l'engage que lui.

  Les clients de l'API se distinguent par l'en-tete X-Cle-Api. Deux cles
  existent : cle-alpha et cle-beta. Des utilisateurs DERRIERE UN NAT
  partagent une adresse IP : regrouper par adresse les penaliserait tous
  pour l'abus d'un seul.

  /public   10 requetes par seconde, avec une rafale de 20 admise
  /admin    2 requetes par seconde, avec une rafale de 5 admise
  corps     1 Mio au plus sur toutes les routes

  Un refus de debit se rend en 429.

  /public et /admin ne doivent PAS partager leur compteur : marteler
  l'administration ne doit pas refuser le trafic public.
TXT
chown student:student "$WORK/politique.txt"
chmod 0644 "$WORK/politique.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 3 --silent --output /dev/null http://127.0.0.1/; then
    echo "Situation posée : une API limitée, et mal."
    exit 0
  fi
  sleep 1
done
echo "Nginx ne répond pas." >&2
exit 1
