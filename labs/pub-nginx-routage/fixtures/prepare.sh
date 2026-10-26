#!/usr/bin/env bash
# Pose la situation : deux server blocks, des locations qui se recouvrent, et
# une page d'administration servie a qui ne la demande pas.
#
# LES QUATRE DEFAUTS POSES, UN PAR CONTROLE
#
#   1. `location /api` en prefixe simple capte aussi /api/v1/..., alors que
#      la regex qui devait les traiter est declaree APRES. Nginx choisit la
#      regex avant le prefixe... sauf si le prefixe porte `^~`, et c'est
#      precisement ce qu'il faut savoir.
#   2. AUCUN server par defaut : le premier server du fichier recoit donc
#      tout nom inconnu, et c'est celui de l'administration.
#   3. Une redirection ecrite avec `rewrite ... redirect` sur le meme
#      prefixe qu'elle vise : elle boucle.
#   4. Rien n'explique la regle de selection, et c'est la le travail.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-routage.log) 2>&1
set -x

WORK=/opt/pub-nginx-routage

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# Un backend unique, qui REND LE GESTIONNAIRE QUI L'A APPELE. C'est ce qui
# permet de mesurer la selection sans lire la configuration : chaque
# location passe son nom en en-tete, et le backend le renvoie.
cat > "$WORK/application.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Application(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        gestionnaire = self.headers.get("X-Gestionnaire", "inconnu")
        corps = f"gestionnaire={gestionnaire} chemin={self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18093), Application).serve_forever()
PY
chmod 0644 "$WORK/application.py"

cat > /etc/systemd/system/pub-nginx-routage-backend.service <<'UNIT'
[Unit]
Description=Backend for the Nginx routing lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-routage/application.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-routage-backend.service

# LA CONFIGURATION FOURNIE, avec ses quatre defauts.
cat > /etc/nginx/conf.d/routage.conf <<'CONF'
# PREMIER server du fichier : sans `default_server` declare ailleurs, c'est
# lui qui recoit tout nom inconnu. Et c'est l'administration.
server {
    listen 80;
    server_name admin.lab.test;

    location / {
        proxy_pass http://127.0.0.1:18093;
        proxy_set_header X-Gestionnaire admin-racine;
        proxy_set_header Host $host;
    }
}

server {
    listen 80;
    server_name app.lab.test;

    # Prefixe simple : il capte /api ET tout ce qui commence par /api.
    location /api {
        proxy_pass http://127.0.0.1:18093;
        proxy_set_header X-Gestionnaire api-prefixe;
        proxy_set_header Host $host;
    }

    # Declaree apres, et sans priorite : elle ne verra jamais /api/v1 tant
    # que la selection n'aura pas ete corrigee.
    location ~ ^/api/v[0-9]+/ {
        proxy_pass http://127.0.0.1:18093;
        proxy_set_header X-Gestionnaire api-versionne;
        proxy_set_header Host $host;
    }

    location /static {
        proxy_pass http://127.0.0.1:18093;
        proxy_set_header X-Gestionnaire statique;
        proxy_set_header Host $host;
    }

    # La redirection qui boucle : elle vise le prefixe dont elle part.
    location /ancien {
        return 301 http://$host/ancien/;
    }

    location / {
        proxy_pass http://127.0.0.1:18093;
        proxy_set_header X-Gestionnaire app-racine;
        proxy_set_header Host $host;
    }
}
CONF

cat > "$WORK/matrice.txt" <<'TXT'
La matrice de selection attendue. Chaque URL doit atteindre le gestionnaire
nomme a droite, et le backend renvoie ce nom dans son corps.

  http://app.lab.test/api            -> api-exact
  http://app.lab.test/api/v1/clients -> api-versionne
  http://app.lab.test/apidoc         -> app-racine
  http://app.lab.test/static/app.js  -> statique
  http://app.lab.test/accueil        -> app-racine

Et deux exigences qui ne sont pas dans la matrice :

  - un nom d'hote INCONNU ne doit servir ni l'application ni
    l'administration ;
  - http://app.lab.test/ancien doit rediriger VERS /nouveau, en conservant
    l'autorite, et sans boucler.

Enfin, ecrivez votre lecture de la regle de selection dans
/home/student/selection.yaml, sous la forme :

  predictions:
    /api: api-exact
    /api/v1/clients: api-versionne
    /apidoc: app-racine
    /static/app.js: statique
    /accueil: app-racine

La validation compare vos predictions a ce que le serveur fait REELLEMENT.
Predire juste sur une configuration fausse ne passe pas, et configurer juste
sans savoir le predire non plus.
TXT
chown student:student "$WORK/matrice.txt"
chmod 0644 "$WORK/matrice.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 2 --silent --output /dev/null \
       -H 'Host: app.lab.test' http://127.0.0.1/accueil; then
    echo "Situation posée : une configuration qui se recouvre."
    exit 0
  fi
  sleep 1
done
echo "Nginx ne répond pas." >&2
exit 1
