#!/usr/bin/env bash
# Pose la situation : Nginx publie l'application, et n'en dit rien.
#
# Le journal d'acces est au format `combined` par defaut, qui ne porte ni le
# temps de reponse ni celui de l'amont : on ne peut donc pas savoir, en le
# lisant, si une lenteur vient de Nginx ou de l'application. Et aucun point
# d'etat n'est expose.
#
# CE QUE CE FICHIER NE FAIT PAS, VOLONTAIREMENT : il ne pose ni `stub_status`,
# ni format de journal structure. Ce sont les gestes que les tests cherchent.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-observation.log) 2>&1
set -x

WORK=/opt/pub-nginx-observation
docker rm -f pub-nginx-observation 2>/dev/null || true
systemctl stop pub-nginx-observation-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-nginx-observation-backend.service
systemctl daemon-reload
for port in 80 8081 18087; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/logs"
docker pull "$IMG_NGINX"

# Le backend sert trois chemins qui donnent au journal quelque chose a dire :
# une reponse immediate, une reponse LENTE, et une erreur. Sans eux, un
# journal structure serait indiscernable d'un journal decoratif.
cat > "$WORK/backend.py" <<'PY'
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LENTEUR = 2.0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/lent"):
            time.sleep(LENTEUR)
        if self.path.startswith("/casse"):
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        corps = f"Nginx observation backend: {self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18087), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-nginx-observation-backend.service <<'UNIT'
[Unit]
Description=Backend for the Nginx observation lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-observation/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-observation-backend.service

# La configuration de depart : elle publie, et elle n'observe rien.
cat > "$WORK/app.conf" <<'CONF'
server {
    listen 80 default_server;
    server_name app.lab.test;

    location / {
        proxy_pass http://127.0.0.1:18087;
        proxy_set_header Host $host;
    }
}
CONF
chmod 0664 "$WORK/app.conf"

cat > "$WORK/compose.yaml" <<YAML
services:
  nginx:
    image: "$IMG_NGINX"
    container_name: pub-nginx-observation
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./app.conf:/etc/nginx/conf.d/default.conf:ro
      - ./logs:/var/log/nginx
YAML

chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-nginx-observation \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      --resolve app.lab.test:80:127.0.0.1 http://app.lab.test/health; then
    echo "Situation posée : Nginx publie l'application, sans rien en dire."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Nginx ou le backend ne répond pas." >&2
exit 1
