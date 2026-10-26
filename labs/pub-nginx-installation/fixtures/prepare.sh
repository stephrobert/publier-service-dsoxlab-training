#!/usr/bin/env bash
# Pose la situation : une VM avec ses outils, et AUCUNE configuration du
# service cible.
#
# Ce lab est le premier de la famille Nginx : il n'herite de rien. Le setup
# installe donc Nginx par le paquet de la distribution, retire la
# configuration de demonstration, et depose le manifeste que la validation
# confrontera a ce qui tourne reellement.
#
# CE QUE LE SETUP NE FAIT PAS : il n'ecrit aucun `server`, n'active aucun
# site, et ne declare rien au demarrage automatique du service cible. Les
# quatre controles portent sur ces gestes.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-installation.log) 2>&1
set -x

WORK=/opt/pub-nginx-installation

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl

# La configuration de demonstration de la distribution repondrait sur le
# port 80 et ferait passer le premier controle sans travail.
rm -f /etc/nginx/sites-enabled/default
install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# Le backend que la configuration cible devra publier.
cat > "$WORK/application.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Application(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        corps = f"Nginx installation backend: {self.path}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18092), Application).serve_forever()
PY
chmod 0644 "$WORK/application.py"

cat > /etc/systemd/system/pub-nginx-installation-backend.service <<'UNIT'
[Unit]
Description=Backend for the Nginx installation lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-installation/application.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-installation-backend.service

# LE MANIFESTE. Il dit ce que l'installation doit presenter, et c'est lui que
# la validation confronte au binaire REELLEMENT en service. Le declarer ici
# plutot que de l'ecrire en dur dans le test permet de le relire, et evite
# qu'un test affirme une version que personne ne peut verifier.
VERSION=$(nginx -v 2>&1 | sed 's/.*nginx\///')
cat > "$WORK/manifeste.txt" <<TXT
Manifeste de l'installation attendue.

  version     : $VERSION
  module      : http_ssl_module (compile dans le paquet de la distribution)
  nom servi   : app.lab.test
  backend     : 127.0.0.1:18092
  fichier     : /etc/nginx/sites-available/app.conf, active par lien
                symbolique dans /etc/nginx/sites-enabled/

Le service doit repondre sur le port 80 pour le nom ci-dessus, et revenir
de lui-meme apres un redemarrage de la machine.
TXT
chown student:student "$WORK/manifeste.txt"
chmod 0644 "$WORK/manifeste.txt"

# Le service est ARRETE et NON active : le remettre en marche et le rendre
# persistant fait partie du travail.
systemctl stop nginx || true
systemctl disable nginx || true

for _ in $(seq 1 20); do
  if curl --max-time 2 --silent --output /dev/null http://127.0.0.1:18092/; then
    echo "Situation posée : Nginx installé, aucun service publié."
    exit 0
  fi
  sleep 1
done
echo "Le backend ne répond pas." >&2
exit 1
