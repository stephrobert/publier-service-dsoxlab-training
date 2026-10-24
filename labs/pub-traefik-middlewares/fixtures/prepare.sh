#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-middlewares.log) 2>&1
set -x

WORK=/opt/pub-middlewares
docker rm -f pub-middlewares-traefik 2>/dev/null || true
systemctl stop pub-middlewares-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-middlewares-backend.service
systemctl daemon-reload
for port in 80 18082; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic"
docker pull "$IMG_TRAEFIK"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"PATH={self.path}\n".encode() + b"x" * 8192
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("127.0.0.1", 18082), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-middlewares-backend.service <<'UNIT'
[Unit]
Description=Backend for the Traefik middleware lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-middlewares/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-middlewares-backend.service

cat > "$WORK/dynamic/base.yaml" <<'YAML'
http:
  routers:
    portal:
      rule: "Host(`middleware.lab.test`) && PathPrefix(`/portal/`)"
      entryPoints:
        - web
      service: backend
    legacy:
      rule: "Host(`middleware.lab.test`) && PathPrefix(`/legacy/`)"
      entryPoints:
        - web
      service: backend
  services:
    backend:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:18082
YAML
chown -R student:docker "$WORK"

docker run -d --name pub-middlewares-traefik \
  --network host \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  "$IMG_TRAEFIK" \
  --entrypoints.web.address=:80 \
  --providers.file.directory=/etc/traefik/dynamic \
  --providers.file.watch=true \
  --log.level=INFO
docker inspect --format '{{.State.StartedAt}}' pub-middlewares-traefik \
  > "$WORK/traefik-started-at"

cat > "$WORK/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-traefik-middlewares.

Traefik écoute sur le port 80 et route déjà les requêtes du nom
middleware.lab.test vers un backend systemd local au proxy. Vous pouvez
consulter et modifier les fichiers dynamiques dans dynamic/.

Le backend répond par le chemin qu'il reçoit et fournit un corps assez long
pour vérifier la compression. Les tests interrogent le proxy sur :
  - /portal/path-check ;
  - /portal/compressed ;
  - /legacy/guide.

Le travail attendu porte sur la transformation des chemins, la redirection,
les en-têtes HTTP de sécurité et la compression des réponses. Les tests
observent les réponses HTTP réellement servies et vérifient que Traefik n'a
pas été redémarré.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null --write-out '%{http_code}' \
    -H 'Host: middleware.lab.test' http://127.0.0.1/portal/path-check | grep -qx 200; then
    echo "Situation posée : le backend et les routes de base répondent."
    exit 0
  fi
  sleep 1
done
docker logs pub-middlewares-traefik
echo "Le backend de démonstration ne répond pas par Traefik." >&2
exit 1
