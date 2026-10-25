#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-mise-a-jour.log) 2>&1
set -x

WORK=/opt/pub-mise-a-jour
docker rm -f pub-mise-a-jour-traefik 2>/dev/null || true
systemctl stop pub-mise-a-jour-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-mise-a-jour-backend.service
systemctl daemon-reload
for port in 80 18086; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic"
docker pull "$IMG_TRAEFIK_PREVIOUS"
docker pull "$IMG_TRAEFIK_CURRENT"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Traefik upgrade backend: available\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", 18086), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-mise-a-jour-backend.service <<'UNIT'
[Unit]
Description=Backend for the Traefik upgrade lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-mise-a-jour/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-mise-a-jour-backend.service

cat > "$WORK/dynamic/routes.yaml" <<'YAML'
http:
  routers:
    upgrade:
      rule: "Host(`typo.lab.test`)"
      entryPoints:
        - web
      service: upgrade-backend
  services:
    upgrade-backend:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18086
YAML

cat > "$WORK/compose.yaml" <<YAML
services:
  traefik:
    image: "$IMG_TRAEFIK_PREVIOUS"
    container_name: pub-mise-a-jour-traefik
    network_mode: host
    restart: unless-stopped
    command:
      - --entrypoints.web.address=:80
      - --providers.file.directory=/etc/traefik/dynamic
      - --providers.file.watch=true
      - --log.level=INFO
    volumes:
      - ./dynamic:/etc/traefik/dynamic:ro
YAML
chown -R student:docker "$WORK"

docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

cat > "$WORK/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-traefik-mise-a-jour.

Traefik publie un backend systemd local avec le fournisseur fichier. La
configuration dynamique, le fichier Compose et les journaux du conteneur sont
disponibles pour l'inspection. La situation initiale utilise Traefik v3.7.6 ;
les modifications doivent préserver le service pendant la mise à niveau.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-mise-a-jour-traefik \
    2>/dev/null | grep -qx true \
    && systemctl is-active --quiet pub-mise-a-jour-backend.service; then
    echo "Situation posée : Traefik et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Traefik ou le backend ne démarre pas." >&2
exit 1
