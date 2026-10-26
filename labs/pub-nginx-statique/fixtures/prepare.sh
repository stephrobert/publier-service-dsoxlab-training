#!/usr/bin/env bash
# Pose la situation : une application monopage, ses ressources, un fichier
# prive, et une configuration qui sert tout ca sans distinction.
#
# LES QUATRE DEFAUTS POSES
#
#   1. aucun type MIME correct : tout part en application/octet-stream,
#      parce que la configuration VIDE la table des types. Omettre
#      `include mime.types` ne suffit pas : voir le bloc `types {}` plus
#      bas, et la mesure qui l'a imposé ;
#   2. le fallback renvoie index.html POUR TOUT, y compris pour une
#      ressource absente et pour l'API : une erreur devient un succes ;
#   3. le fichier prive et les dotfiles sont servis ;
#   4. les permissions sont ouvertes a tous (0777), ce qui marche et ne
#      devrait pas.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-statique.log) 2>&1
set -x

WORK=/opt/pub-nginx-statique
RACINE_WEB=$WORK/site

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0777 "$RACINE_WEB" "$RACINE_WEB/assets"

printf '%s\n' '<!doctype html><html><head><meta charset="utf-8">' \
  '<title>Application</title></head><body><div id="app"></div>' \
  '<script src="/assets/app.js"></script></body></html>' \
  > "$RACINE_WEB/index.html"
printf 'console.log("application monopage");\n' > "$RACINE_WEB/assets/app.js"
printf 'body { font-family: sans-serif; }\n' > "$RACINE_WEB/assets/app.css"

# Le fichier prive, et un dotfile : ni l'un ni l'autre ne doit sortir.
printf 'CLE_API=secret-ne-doit-jamais-sortir-4f21\n' > "$RACINE_WEB/.env"
printf 'mot de passe de deploiement : secret-prive-8a33\n' \
  > "$RACINE_WEB/deploiement.interne"

chmod -R 0777 "$RACINE_WEB"

# Le backend d'API : le fallback ne doit JAMAIS le remplacer par index.html.
cat > "$WORK/api.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Api(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/api/existe"):
            corps, statut = b'{"ok": true}\n', 200
        else:
            corps, statut = b'{"erreur": "inconnu"}\n', 404
        self.send_response(statut)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18094), Api).serve_forever()
PY
chmod 0644 "$WORK/api.py"

cat > /etc/systemd/system/pub-nginx-statique-api.service <<'UNIT'
[Unit]
Description=API backend for the Nginx static lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-statique/api.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-statique-api.service

# LA CONFIGURATION FOURNIE, avec ses quatre defauts.
cat > /etc/nginx/conf.d/statique.conf <<'CONF'
server {
    listen 80 default_server;
    server_name app.lab.test;
    root /opt/pub-nginx-statique/site;

    # LA TABLE DES TYPES EST VIDÉE ICI, et c'est ce qui pose le défaut.
    #
    # Omettre `include mime.types` ne suffisait pas. Mesure du 2026-10-26 :
    # le premier contrôle du lab passait AVANT tout travail, parce que le
    # `nginx.conf` du paquet de l'éditeur inclut `/etc/nginx/mime.types`
    # au niveau `http`. Un `server` qui se contente de ne pas l'inclure
    # HÉRITE donc de la table, et `/assets/app.js` sortait bel et bien en
    # `application/javascript`. Un `types {}` vide au niveau `server`
    # REMPLACE la table héritée : tout repart alors en
    # `application/octet-stream`, c'est-à-dire le défaut que le lab
    # prétend enseigner.
    types { }
    default_type application/octet-stream;

    # Le fallback avale TOUT, y compris les ressources absentes et l'API.
    location / {
        try_files $uri $uri/ /index.html;
    }
}
CONF

cat > "$WORK/attendu.txt" <<'TXT'
Ce que la publication doit presenter.

  /                      index.html, type text/html
  /assets/app.js         type application/javascript (ou text/javascript)
  /assets/app.css        type text/css
  /accueil               index.html : c'est le fallback de l'application
                         monopage, et il est legitime ICI
  /assets/absent.js      404 : une ressource absente reste une erreur
  /api/existe            200 de l'API
  /api/inconnu           404 de l'API, et surtout PAS index.html
  /.env                  refuse
  /deploiement.interne   refuse
  /../../etc/passwd      refuse

Et une exigence qui ne se lit pas dans une reponse HTTP : les fichiers ne
doivent pas etre lisibles par tout le monde sur le disque. Les workers de
Nginx tournent sous le compte `nginx` (c'est le paquet de l'editeur qui est
installe ici, et son nginx.conf porte `user nginx;`) ; ils doivent pouvoir
lire ce qu'ils servent, et rien de plus large.
TXT
chown student:student "$WORK/attendu.txt"
chmod 0644 "$WORK/attendu.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 2 --silent --output /dev/null \
       -H 'Host: app.lab.test' http://127.0.0.1/; then
    echo "Situation posée : tout est servi, sans distinction."
    exit 0
  fi
  sleep 1
done
echo "Nginx ne répond pas." >&2
exit 1
