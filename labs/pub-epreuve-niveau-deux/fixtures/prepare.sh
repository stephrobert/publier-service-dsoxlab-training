#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-epreuve-niveau-deux.log) 2>&1
set -x

WORK=/opt/pub-epreuve-niveau-deux
docker rm -f pub-e2-traefik pub-e2-prometheus 2>/dev/null || true
systemctl stop pub-epreuve-niveau-deux-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-epreuve-niveau-deux-backend.service
systemctl daemon-reload
for port in 80 443 8082 9090 18087; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker \
  "$WORK/dynamic" "$WORK/prometheus" "$WORK/logs" "$WORK/tls"
docker pull "$IMG_TRAEFIK"
docker pull "$IMG_PROMETHEUS"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = 503 if self.path == "/incident" else 200
        body = f"E2 backend: {self.path}\n".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", 18087), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-epreuve-niveau-deux-backend.service <<'UNIT'
[Unit]
Description=Backend for the level two Traefik assessment
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-epreuve-niveau-deux/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-epreuve-niveau-deux-backend.service

openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
  -keyout "$WORK/tls/lab.key" -out "$WORK/tls/lab.crt" \
  -subj '/CN=app.lab.test' \
  -addext 'subjectAltName=DNS:app.lab.test,DNS:admin.lab.test'
openssl passwd -apr1 -salt pube2 'E2-Observe-2026' \
  | sed 's/^/operator:/' > "$WORK/credentials.htpasswd"
chmod 0644 "$WORK/tls/lab.crt" "$WORK/credentials.htpasswd"
chmod 0640 "$WORK/tls/lab.key"

cat > "$WORK/dynamic.yaml" <<'YAML'
http:
  routers:
    app:
      rule: "Host(`app.lab.test`)"
      entryPoints:
        - websecure
      service: app-backend
      tls: {}
    admin:
      rule: "Host(`admin.lab.test`) && (PathPrefix(`/api`) || PathPrefix(`/dashboard`))"
      entryPoints:
        - web
      service: api@internal
  services:
    app-backend:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18088
tls:
  certificates:
    - certFile: /etc/traefik/tls/lab.crt
      keyFile: /etc/traefik/tls/lab.key
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
    container_name: pub-e2-traefik
    network_mode: host
    restart: unless-stopped
    command:
      - --api=true
      - --api.dashboard=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --providers.file.filename=/etc/traefik/dynamic.yaml
      - --providers.file.watch=true
      - --log.level=INFO
    volumes:
      - ./dynamic.yaml:/etc/traefik/dynamic.yaml:ro
      - ./credentials.htpasswd:/etc/traefik/credentials.htpasswd:ro
      - ./tls:/etc/traefik/tls:ro
      - ./logs:/var/log/traefik
  prometheus:
    image: "$IMG_PROMETHEUS"
    container_name: pub-e2-prometheus
    network_mode: host
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --web.listen-address=127.0.0.1:9090
      - --web.enable-lifecycle
    volumes:
      - ./prometheus:/etc/prometheus:ro
YAML
chown -R student:docker "$WORK"

cat > "$WORK/LISEZ-MOI.txt" <<'TXT'
Répertoire de l'épreuve pub-epreuve-niveau-deux.

Le backend est un service systemd local. /incident renvoie délibérément HTTP
503 ; les autres chemins renvoient HTTP 200. Les fichiers à inspecter sont
dynamic.yaml, compose.yaml et prometheus/.

Les routes sont app.lab.test et admin.lab.test. Le compte de test pour
l'administration est operator / E2-Observe-2026. Le certificat de laboratoire
est autosigné ; les clients de test doivent faire confiance à ce certificat ou
désactiver la vérification TLS.

Prometheus écoute sur 127.0.0.1:9090. Traefik devrait exposer ses métriques
uniquement sur 127.0.0.1:8082. Le dossier logs/ reçoit les journaux JSON.
Rédigez le diagnostic dans incident-report.txt à la racine de ce répertoire.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d
for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-e2-traefik \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      http://127.0.0.1:9090/-/ready; then
    date +%s > "$WORK/assessment-started-at"
    chown student:docker "$WORK/assessment-started-at"
    echo "Situation posée : la pile de l'épreuve est active."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Traefik ou Prometheus ne répond pas." >&2
exit 1
