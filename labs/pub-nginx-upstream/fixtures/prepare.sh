#!/usr/bin/env bash
# Pose la situation : deux backends identifiables, pilotables, et une
# repartition qui ne detecte rien et rejoue tout.
#
# LES DEFAUTS POSES
#   1. `max_fails=0` DESACTIVE la detection passive. Un backend en erreur
#      continue de recevoir sa part du trafic, indefiniment.
#   2. `proxy_next_upstream` porte `non_idempotent` : un POST dont la
#      reponse echoue est REJOUE sur l'autre backend, et l'action est
#      comptee deux fois.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-upstream.log) 2>&1
set -x

WORK=/opt/pub-nginx-upstream

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# Le compteur metier, partage par les deux backends : c'est lui, et lui
# seul, qui dit si une action a ete comptee deux fois.
echo '{"commandes": 0}' > "$WORK/commandes.json"
chmod 0666 "$WORK/commandes.json"

# Le mode de chaque backend, pilotable par un simple fichier.
echo ok > "$WORK/mode-a.txt"
echo ok > "$WORK/mode-b.txt"
chmod 0666 "$WORK/mode-a.txt" "$WORK/mode-b.txt"

cat > "$WORK/backend.py" <<'PY'
import json
import os
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])
RACINE = pathlib.Path("/opt/pub-nginx-upstream")
MODE = RACINE / f"mode-{NOM}.txt"
COMPTEUR = RACINE / "commandes.json"
VERROU = threading.Lock()


def mode() -> str:
    try:
        return MODE.read_text(encoding="utf-8").strip() or "ok"
    except OSError:
        return "ok"


class Backend(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        courant = mode()
        if courant == "lent":
            time.sleep(8)
        if courant == "erreur":
            self._repondre(502, f"backend={NOM} en erreur\n")
            return
        self._repondre(200, f"backend={NOM}\n")

    def do_POST(self):
        # L'ACTION A LIEU D'ABORD, l'echec vient ensuite : c'est le cas qui
        # piege un rejeu. Le backend a ecrit, le client ne le sait pas.
        with VERROU:
            etat = json.loads(COMPTEUR.read_text(encoding="utf-8"))
            etat["commandes"] = int(etat.get("commandes", 0)) + 1
            COMPTEUR.write_text(json.dumps(etat), encoding="utf-8")
        if mode() == "erreur":
            self._repondre(502, f"backend={NOM} a ecrit puis echoue\n")
            return
        self._repondre(200, f"backend={NOM} a enregistre\n")

    def _repondre(self, statut, corps):
        octets = corps.encode()
        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(octets)))
        self.end_headers()
        self.wfile.write(octets)

    def log_message(self, *args):
        return


os.umask(0)
ThreadingHTTPServer(("127.0.0.1", PORT), Backend).serve_forever()
PY
chmod 0644 "$WORK/backend.py"

for duo in "a 18095" "b 18096"; do
  set -- $duo
  cat > "/etc/systemd/system/pub-nginx-upstream-$1.service" <<UNIT
[Unit]
Description=Backend $1 for the Nginx upstream lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-upstream/backend.py $1 $2
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
done
systemctl daemon-reload
systemctl enable --now pub-nginx-upstream-a.service pub-nginx-upstream-b.service

cat > /etc/nginx/conf.d/upstream.conf <<'CONF'
upstream applicatif {
    # max_fails=0 DESACTIVE la detection passive : un backend en erreur
    # garde sa part du trafic, pour toujours.
    server 127.0.0.1:18095 max_fails=0;
    server 127.0.0.1:18096 max_fails=0;
}

server {
    listen 80 default_server;
    server_name app.lab.test;

    location / {
        proxy_pass http://applicatif;
        proxy_set_header Host $host;
        # `non_idempotent` autorise le rejeu d'un POST dont la reponse a
        # echoue. L'action peut alors etre comptee deux fois.
        proxy_next_upstream error timeout http_502 non_idempotent;
        proxy_connect_timeout 2s;
        proxy_read_timeout 15s;
    }
}
CONF
  /etc/nginx/conf.d/upstream.conf

cat > "$WORK/banc.txt" <<'TXT'
Le banc de repartition.

  deux backends : a sur 127.0.0.1:18095, b sur 127.0.0.1:18096
  chacun rend son nom dans le corps : backend=a ou backend=b

Pilotage, en ecrivant un mot dans le fichier :

  echo ok     > /opt/pub-nginx-upstream/mode-a.txt   repond normalement
  echo erreur > /opt/pub-nginx-upstream/mode-a.txt   repond 502
  echo lent   > /opt/pub-nginx-upstream/mode-a.txt   repond au bout de 8 s

Un POST sur / incremente le compteur metier AVANT de savoir s'il repondra :
en mode erreur, le backend a donc ecrit puis echoue. Le compteur est dans
/opt/pub-nginx-upstream/commandes.json.

RAPPEL SUR LE BUILD OPEN SOURCE : il n'a PAS de sonde active. La seule
detection disponible est passive, par `max_fails` et `fail_timeout` sur la
ligne `server` de l'upstream. Un backend n'est donc retire qu'apres avoir
fait echouer de vraies requetes de clients.
TXT
chown student:student "$WORK/banc.txt"
chmod 0644 "$WORK/banc.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 3 --silent --output /dev/null http://127.0.0.1/; then
    echo "Situation posée : deux backends, aucune détection, rejeu autorisé."
    exit 0
  fi
  sleep 1
done
echo "Nginx ne répond pas." >&2
exit 1
