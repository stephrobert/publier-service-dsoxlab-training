#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-tls.log) 2>&1
set -x

WORK=/opt/pub-haproxy-tls
docker rm -f pub-haproxy-tls 2>/dev/null || true
systemctl stop pub-haproxy-tls-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-haproxy-tls-backend.service
systemctl daemon-reload
for port in 80 443 18085; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker \
  "$WORK/certs" "$WORK/run" "$WORK/logs"
docker pull "$IMG_HAPROXY"

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

cat > /etc/systemd/system/pub-haproxy-tls-backend.service <<'UNIT'
[Unit]
Description=Backend for the HAProxy TLS lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-haproxy-tls/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-haproxy-tls-backend.service

openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
  -keyout "$WORK/certs/wrong.key" -out "$WORK/certs/wrong.crt" \
  -subj '/CN=wrong.lab.test' -addext 'subjectAltName=DNS:wrong.lab.test'
cat "$WORK/certs/wrong.key" "$WORK/certs/wrong.crt" \
  > "$WORK/certs/wrong.pem"
chmod 0644 "$WORK/certs/wrong.pem"
openssl genrsa -out "$WORK/account.key" 2048
chmod 0644 "$WORK/account.key"

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
  bind :443 ssl crt /etc/haproxy/certs/wrong.pem ssl-min-ver TLSv1.0
  default_backend app

backend app
  server app 127.0.0.1:18085 check
CFG

cat > "$WORK/compose.yaml" <<YAML
services:
  haproxy:
    image: "$IMG_HAPROXY"
    container_name: pub-haproxy-tls
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
      - ./account.key:/etc/haproxy/account.key
      - ./certs:/etc/haproxy/certs
      - ./run:/run/haproxy
      - /opt/pub-traefik-acme/pebble.minica.pem:/etc/haproxy/pebble.minica.pem:ro
      - /opt/pub-traefik-acme/pebble-root.pem:/etc/haproxy/pebble-root.pem:ro
YAML
chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

cat > "$WORK/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-haproxy-tls.

HAProxy 3.4 publie le backend systemd local sur les ports 80 et 443. La
configuration fournie ne configure pas ACME et utilise un mauvais certificat.
Le fichier à modifier est haproxy.cfg ; l'image et le déploiement sont déjà
définis dans compose.yaml.

Pebble répond sur https://localhost:14000/dir. L'autorité de test ne sert que
des certificats de courte durée pour rendre le renouvellement observable.
Le compte HAProxy doit utiliser /etc/haproxy/account.key. Le répertoire
/run/haproxy/ est partagé avec le conteneur pour sa socket d'administration.

Le backend attendu écoute sur 127.0.0.1:18085. Les tests interrogent
app.lab.test avec SNI et Host correspondant.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-haproxy-tls \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      http://127.0.0.1:80/; then
    date +%s > "$WORK/haproxy-started-at"
    chown student:docker "$WORK/haproxy-started-at"
    echo "Situation posée : HAProxy et le backend sont actifs."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "HAProxy ou le backend ne répond pas." >&2
exit 1
