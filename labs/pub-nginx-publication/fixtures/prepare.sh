#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-publication.log) 2>&1
set -x

WORK=/opt/pub-nginx-publication
docker rm -f pub-nginx-publication 2>/dev/null || true
systemctl stop pub-nginx-publication-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-nginx-publication-backend.service
systemctl daemon-reload
for port in 80 18085; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
docker pull "$IMG_NGINX"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            f"Nginx backend: {self.path}\n"
            f"Host: {self.headers.get('Host', '')}\n"
            f"X-Forwarded-For: {self.headers.get('X-Forwarded-For', '')}\n"
            f"X-Forwarded-Proto: {self.headers.get('X-Forwarded-Proto', '')}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", 18085), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-nginx-publication-backend.service <<'UNIT'
[Unit]
Description=Backend for the Nginx publication lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-publication/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-publication-backend.service

cat > "$WORK/nginx.conf" <<'CFG'
events {}

http {
  server {
    listen 80;
    server_name app.lab.test;
    location / {
      return 503;
    }
  }
}
CFG

cat > "$WORK/compose.yaml" <<YAML
services:
  nginx:
    image: "$IMG_NGINX"
    container_name: pub-nginx-publication
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
YAML

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Répertoire de travail du lab pub-nginx-publication.

Modifiez nginx.conf, puis appliquez la configuration au conteneur Nginx déjà
défini dans compose.yaml.

Le backend écoute uniquement sur l'hôte, à 127.0.0.1:18085. Il renvoie le
chemin, l'en-tête Host et les en-têtes de transfert qu'il reçoit.

Image Nginx épinglée :
  $IMG_NGINX
TXT

chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-nginx-publication \
    2>/dev/null | grep -qx true \
    && timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/80" 2>/dev/null; then
    echo "Situation posée : Nginx et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Nginx ou le backend ne répond pas." >&2
exit 1
