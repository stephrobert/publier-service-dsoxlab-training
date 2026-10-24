#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-observabilite.log) 2>&1
set -x

WORK=/opt/pub-haproxy-observabilite
docker rm -f pub-haproxy-observabilite pub-haproxy-observabilite-prometheus \
  2>/dev/null || true
systemctl stop pub-haproxy-observabilite-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-haproxy-observabilite-backend.service
systemctl daemon-reload
for port in 80 8404 9090 18085; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/run" "$WORK/prometheus"
docker pull "$IMG_HAPROXY"
docker pull "$IMG_PROMETHEUS"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"HAProxy backend: {self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", 18085), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-haproxy-observabilite-backend.service <<'UNIT'
[Unit]
Description=Backend for the HAProxy observability lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-haproxy-observabilite/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-haproxy-observabilite-backend.service

cat > "$WORK/prometheus.yml" <<'PROM'
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: haproxy
    static_configs:
      - targets:
          - 127.0.0.1:8404
    metrics_path: /metrics
PROM

cat > "$WORK/haproxy.cfg" <<'CFG'
global
  log stdout format raw local0
  stats socket /run/haproxy/admin.sock mode 660 level admin

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

frontend metrics
  bind :8404
  http-request return status 404

backend app
  server app 127.0.0.1:18085 check
CFG

cat > "$WORK/compose.yaml" <<YAML
services:
  haproxy:
    image: "$IMG_HAPROXY"
    container_name: pub-haproxy-observabilite
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
  prometheus:
    image: "$IMG_PROMETHEUS"
    container_name: pub-haproxy-observabilite-prometheus
    network_mode: host
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --web.listen-address=0.0.0.0:9090
      - --storage.tsdb.path=/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
YAML

chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-haproxy-observabilite \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      http://127.0.0.1:80/ \
    && curl --max-time 2 --silent --output /dev/null \
      http://127.0.0.1:9090/-/ready; then
    echo "Situation posée : HAProxy, Prometheus et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "HAProxy, Prometheus ou le backend ne répond pas." >&2
exit 1
