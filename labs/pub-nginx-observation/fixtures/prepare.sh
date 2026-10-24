#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-observation.log) 2>&1
set -x

WORK=/opt/pub-nginx-observation
docker rm -f pub-nginx-observation 2>/dev/null || true
systemctl stop pub-nginx-observation-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-nginx-observation-backend.service
systemctl daemon-reload
for port in 80 8081 18085; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0777 "$WORK/logs"
docker pull "$IMG_NGINX"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"Nginx observation backend: {self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("127.0.0.1", 18085), Handler).serve_forever()
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

cat > "$WORK/nginx.conf" <<'CFG'
events {}

http {
  access_log /var/log/nginx/access.log;

  server {
    listen 80;
    server_name app.lab.test;

    location / {
      proxy_pass http://127.0.0.1:18085;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
    }
  }
}
CFG

cat > "$WORK/compose.yaml" <<YAML
services:
  nginx:
    image: "$IMG_NGINX"
    container_name: pub-nginx-observation
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
YAML

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Répertoire de travail du lab pub-nginx-observation.

Le fichier à modifier est nginx.conf. Le conteneur Nginx et son backend local
sont déjà en service. Le répertoire logs est monté dans /var/log/nginx du
conteneur. Le backend écoute sur 127.0.0.1:18085.

Image Nginx épinglée :
  $IMG_NGINX
TXT

chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-nginx-observation \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      -H 'Host: app.lab.test' http://127.0.0.1:80/; then
    echo "Situation posée : Nginx et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Nginx ou le backend ne répond pas." >&2
exit 1
