#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-depannage.log) 2>&1
set -x

WORK=/opt/pub-depannage
docker rm -f pub-depannage-traefik 2>/dev/null || true
systemctl stop pub-depannage-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-depannage-backend.service
systemctl daemon-reload
for port in 80 443 18085; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic" "$WORK/tls" "$WORK/logs"
docker pull "$IMG_TRAEFIK"

openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
  -keyout "$WORK/tls/expected.key" -out "$WORK/tls/expected.crt" \
  -subj '/CN=tls.lab.test' -addext 'subjectAltName=DNS:tls.lab.test'
openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
  -keyout "$WORK/tls/wrong.key" -out "$WORK/tls/wrong.crt" \
  -subj '/CN=wrong.lab.test' -addext 'subjectAltName=DNS:wrong.lab.test'

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import sleep


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/slow":
            sleep(5)
        body = f"PATH={self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", 18085), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-depannage-backend.service <<'UNIT'
[Unit]
Description=Backend for the Traefik troubleshooting lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-depannage/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-depannage-backend.service

cat > "$WORK/dynamic/routes-404.yaml" <<'YAML'
http:
  routers:
    notfound:
      rule: "Host(`typo.lab.test`)"
      entryPoints:
        - web
      service: backend-notfound
  services:
    backend-notfound:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18085
YAML

cat > "$WORK/dynamic/routes-502.yaml" <<'YAML'
http:
  routers:
    badgateway:
      rule: "Host(`badgateway.lab.test`)"
      entryPoints:
        - web
      service: backend-badgateway
  services:
    backend-badgateway:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18086
YAML

cat > "$WORK/dynamic/routes-504.yaml" <<'YAML'
http:
  routers:
    timeout:
      rule: "Host(`timeout.lab.test`)"
      entryPoints:
        - web
      service: backend-timeout
  services:
    backend-timeout:
      loadBalancer:
        serversTransport: impatient
        servers:
          - url: http://127.0.0.1:18085
  serversTransports:
    impatient:
      forwardingTimeouts:
        responseHeaderTimeout: 1s
YAML

cat > "$WORK/dynamic/routes-tls.yaml" <<'YAML'
http:
  routers:
    secure:
      rule: "Host(`tls.lab.test`)"
      entryPoints:
        - websecure
      service: backend-secure
      tls: {}
  services:
    backend-secure:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18085
tls:
  certificates:
    - certFile: /etc/traefik/tls/wrong.crt
      keyFile: /etc/traefik/tls/wrong.key
YAML

cat > "$WORK/dynamic/routes-loop.yaml" <<'YAML'
http:
  routers:
    loop-http:
      rule: "Host(`loop.lab.test`)"
      entryPoints:
        - web
      middlewares:
        - to-https
      service: backend-loop
    loop-https:
      rule: "Host(`loop.lab.test`)"
      entryPoints:
        - websecure
      middlewares:
        - to-http
      service: backend-loop
      tls: {}
  middlewares:
    to-https:
      redirectScheme:
        scheme: https
        permanent: true
    to-http:
      redirectScheme:
        scheme: http
        permanent: true
  services:
    backend-loop:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18085
YAML

cat > "$WORK/compose.yaml" <<YAML
services:
  traefik:
    image: "$IMG_TRAEFIK"
    container_name: pub-depannage-traefik
    network_mode: host
    restart: unless-stopped
    command:
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --providers.file.directory=/etc/traefik/dynamic
      - --providers.file.watch=true
      - --log.level=INFO
      - --log.format=json
      - --log.filepath=/var/log/traefik/traefik.json
      - --accesslog=true
      - --accesslog.format=json
      - --accesslog.filepath=/var/log/traefik/access.json
    volumes:
      - ./dynamic:/etc/traefik/dynamic:ro
      - ./tls:/etc/traefik/tls:ro
      - ./logs:/var/log/traefik
YAML
chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

cat > "$WORK/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-traefik-depannage.

Traefik publie le backend systemd local sur plusieurs noms d'hôte. Des erreurs
ont été injectées dans les règles du fournisseur fichier, les services,
l'option de transport, le certificat servi et les redirections.

Les configurations dynamiques modifiables sont dans dynamic/. Traefik les
surveille et les recharge sans redémarrage. Les journaux du proxy sont dans
logs/traefik.json et logs/access.json ; vous pouvez aussi consulter
`docker logs pub-depannage-traefik`.

Les tests interrogent les hôtes notfound.lab.test, badgateway.lab.test,
timeout.lab.test, tls.lab.test et loop.lab.test. Le chemin /slow attend avant
de répondre afin de rendre observable une expiration de délai.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-depannage-traefik \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      http://127.0.0.1:80/; then
    docker inspect --format '{{.State.StartedAt}}' pub-depannage-traefik \
      > "$WORK/traefik-started-at"
    echo "Situation posée : Traefik et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Traefik ou le backend ne répond pas." >&2
exit 1
