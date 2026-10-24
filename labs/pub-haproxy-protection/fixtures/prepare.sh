#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-protection.log) 2>&1
set -x

WORK=/opt/pub-haproxy-protection
docker rm -f pub-haproxy-protection 2>/dev/null || true
systemctl stop pub-haproxy-protection-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-haproxy-protection-backend.service
systemctl daemon-reload
for port in 80 18085; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/run"
docker pull "$IMG_HAPROXY"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"HAProxy protection backend: {self.path}\n".encode()
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

cat > /etc/systemd/system/pub-haproxy-protection-backend.service <<'UNIT'
[Unit]
Description=Backend for the HAProxy protection lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-haproxy-protection/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-haproxy-protection-backend.service

cat > "$WORK/haproxy.cfg" <<'CFG'
global
  log stdout format raw local0

defaults
  log global
  mode http
  option httplog
  timeout connect 5s
  timeout client 30s
  timeout server 30s

frontend web
  bind :80
  default_backend app

backend app
  server app 127.0.0.1:18085 check
CFG

cat > "$WORK/compose.yaml" <<YAML
services:
  haproxy:
    image: "$IMG_HAPROXY"
    container_name: pub-haproxy-protection
    network_mode: host
    user: "0:0"
    cap_add:
      - NET_BIND_SERVICE
    restart: unless-stopped
    command:
      - -W
      - -db
      - -f
      - /usr/local/etc/haproxy/haproxy.cfg
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
      - ./run:/run/haproxy
YAML

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Répertoire de travail du lab pub-haproxy-protection.

Le fichier à modifier est haproxy.cfg. Le conteneur HAProxy et son backend
local sont déjà en service. Le backend écoute sur 127.0.0.1:18085.

Image HAProxy épinglée :
  $IMG_HAPROXY
TXT

chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-haproxy-protection \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null http://127.0.0.1:80/; then
    echo "Situation posée : HAProxy et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "HAProxy ou le backend ne répond pas." >&2
exit 1
