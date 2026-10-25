#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-observabilite.log) 2>&1
set -x

WORK=/opt/pub-observabilite
docker rm -f pub-observabilite-traefik pub-observabilite-prometheus 2>/dev/null || true
systemctl stop pub-observabilite-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-observabilite-backend.service
systemctl daemon-reload
for port in 80 8082 9090 18083; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/logs" "$WORK/prometheus"
docker pull "$IMG_TRAEFIK"
docker pull "$IMG_PROMETHEUS"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = 503 if self.path == "/fail" else 200
        body = f"PATH={self.path}\n".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("127.0.0.1", 18083), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-observabilite-backend.service <<'UNIT'
[Unit]
Description=Backend for the Traefik observability lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-observabilite/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-observabilite-backend.service

cat > "$WORK/dynamic.yaml" <<'YAML'
http:
  routers:
    observabilite:
      rule: "Host(`observabilite.lab.test`)"
      entryPoints:
        - web
      service: backend
  services:
    backend:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18083
YAML

cat > "$WORK/prometheus/prometheus.yml" <<'YAML'
global:
  scrape_interval: 2s
  evaluation_interval: 2s

rule_files:
  - /etc/prometheus/alerts.yml

scrape_configs:
  - job_name: traefik
    static_configs:
      - targets:
          - 127.0.0.1:8082
YAML

cat > "$WORK/prometheus/alerts.yml" <<'YAML'
groups: []
YAML

cat > "$WORK/compose.yaml" <<YAML
services:
  traefik:
    image: "$IMG_TRAEFIK"
    container_name: pub-observabilite-traefik
    network_mode: host
    restart: unless-stopped
    command:
      - --entrypoints.web.address=:80
      - --providers.file.filename=/etc/traefik/dynamic.yaml
      - --providers.file.watch=true
      - --log.level=INFO
    volumes:
      - ./dynamic.yaml:/etc/traefik/dynamic.yaml:ro
      - ./logs:/var/log/traefik
  prometheus:
    image: "$IMG_PROMETHEUS"
    container_name: pub-observabilite-prometheus
    network_mode: host
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --web.listen-address=127.0.0.1:9090
      - --web.enable-lifecycle
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus:/etc/prometheus:ro
YAML
chown -R student:docker "$WORK"

docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

cat > "$WORK/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-traefik-observabilite.

Traefik route observabilite.lab.test vers un backend systemd local.
L'endpoint /fail du backend répond volontairement HTTP 503 ; les autres
chemins répondent HTTP 200.

Les fichiers à examiner et modifier sont compose.yaml et
prometheus/alerts.yml. Prometheus écoute uniquement sur 127.0.0.1:9090 ;
sa configuration scrape déjà l'endpoint métrique local prévu pour Traefik.
Le répertoire logs/ est monté dans Traefik pour recevoir les journaux.

Les tests interrogent le proxy avec les noms d'hôte suivants :
  - observabilite.lab.test pour les réponses 200 et 503 ;
  - 127.0.0.1:9090 pour l'état de la cible et des alertes Prometheus.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

for _ in $(seq 1 45); do
  if curl --max-time 2 --silent --output /dev/null --write-out '%{http_code}' \
    -H 'Host: observabilite.lab.test' http://127.0.0.1/ | grep -qx 200 \
    && curl --max-time 2 --silent --output /dev/null \
      http://127.0.0.1:9090/-/ready; then
    echo "Situation posée : le backend, Traefik et Prometheus répondent."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Le backend ou Prometheus ne répond pas." >&2
exit 1
