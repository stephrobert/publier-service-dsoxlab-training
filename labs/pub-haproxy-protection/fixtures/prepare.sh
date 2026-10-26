#!/usr/bin/env bash
# Pose la situation : HAProxy publie l'application, et ne la protege en rien.
# Aucun en-tete de securite, /admin ouvert a tous, aucune limite de debit, et
# les methodes d'ecriture passent jusqu'au backend.
#
# CE QUE CE FICHIER NE FAIT PAS, ET C'EST VOLONTAIRE : il ne met aucune des
# quatre protections. Ce sont elles que les tests cherchent, et un setup qui
# en poserait une rendrait son test vert sans travail de l'apprenant.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-protection.log) 2>&1
set -x

WORK=/opt/pub-haproxy-protection
docker rm -f pub-haproxy-protection 2>/dev/null || true
systemctl stop pub-haproxy-protection-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-haproxy-protection-backend.service
systemctl daemon-reload
for port in 80 18086; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/run"
docker pull "$IMG_HAPROXY"

# Le backend repond a tout chemin et nomme la methode employee : c'est ce qui
# permet aux tests de distinguer « HAProxy a refuse » de « le backend a
# repondu », au lieu de lire un code de statut sans savoir qui l'a emis.
cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _repondre(self):
        corps = (
            f"HAProxy protection backend: {self.path} "
            f"({self.command})\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corps)

    do_GET = _repondre
    do_HEAD = _repondre
    do_POST = _repondre
    do_PUT = _repondre
    do_DELETE = _repondre

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18086), Handler).serve_forever()
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

# La configuration de depart : elle marche, et elle ne protege rien.
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

backend app
  server app 127.0.0.1:18086 check
CFG
chmod 0664 "$WORK/haproxy.cfg"

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

chown -R student:docker "$WORK"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for _ in $(seq 1 45); do
  if docker inspect --format '{{.State.Running}}' pub-haproxy-protection \
    2>/dev/null | grep -qx true \
    && curl --max-time 2 --silent --output /dev/null \
      --resolve app.lab.test:80:127.0.0.1 http://app.lab.test/health; then
    echo "Situation posée : HAProxy publie l'application, sans aucune protection."
    exit 0
  fi
  sleep 1
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "HAProxy ou le backend ne répond pas." >&2
exit 1
