#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-fichier.log) 2>&1
set -x

WORK=/opt/pub-fichier
if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/80' 2>/dev/null; then
  echo "Le port 80 est déjà occupé avant la mise en situation." >&2
  exit 1
fi
docker rm -f pub-fichier-traefik 2>/dev/null || true
systemctl stop pub-fichier-backend.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-fichier-backend.service
systemctl daemon-reload

install -d -m 0775 -o student -g docker "$WORK/dynamic"
find "$WORK" -mindepth 1 -delete
docker pull "$IMG_TRAEFIK"

cat > "$WORK/backend.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"systemd backend is healthy\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("127.0.0.1", 18081), Handler).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

cat > /etc/systemd/system/pub-fichier-backend.service <<'UNIT'
[Unit]
Description=Web backend for the Traefik file-provider lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-fichier/backend.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-fichier-backend.service

docker run -d --name pub-fichier-traefik \
  --network host \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  "$IMG_TRAEFIK" \
  --entrypoints.web.address=:80 \
  --providers.file.directory=/etc/traefik/dynamic \
  --providers.file.watch=true \
  --log.level=INFO

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null \
    --write-out '%{http_code}' http://127.0.0.1/ | grep -qx 404; then
    break
  fi
  sleep 1
done

started_at=$(docker inspect --format '{{.State.StartedAt}}' pub-fichier-traefik)
printf '%s\n' "$started_at" > "$WORK/traefik-started-at"
cat > "$WORK/README" <<'TXT'
Répertoire de travail du lab pub-traefik-fichier.

Traefik tourne déjà avec son fournisseur fichier dynamique. Le backend
systemd répond sur http://127.0.0.1:18081/ depuis la machine et affiche
"systemd backend is healthy".

Votre configuration dynamique doit publier le service sous
http://systemd.lab.test/. Déposez les fichiers de routage dans le répertoire
dynamic/. Les tests appellent le véritable endpoint HTTP et vérifient que le
conteneur Traefik n'a pas été redémarré depuis le début du lab.
TXT
chown -R student:docker "$WORK"
echo "Situation posée : backend systemd actif, Traefik actif, route absente."
