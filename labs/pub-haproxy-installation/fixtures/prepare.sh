#!/usr/bin/env bash
# Pose la situation : HAProxy installe, ses trois services en marche, et
# AUCUNE configuration de mission.
#
# CE QUE LE SETUP NE FAIT PAS : il n'ecrit ni `frontend`, ni `backend`, ni
# `listen`, ne declare aucun socket d'administration, et ne demande pas le
# demarrage automatique du service. Les quatre controles portent sur ces
# gestes. Une configuration sans listener n'est d'ailleurs pas chargeable :
# `haproxy -c` la refuse en nommant l'absence, ce qui est le premier message
# que l'apprenant doit savoir lire.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-installation.log) 2>&1
set -x

WORK=/opt/pub-haproxy-installation

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# ---------------------------------------------------------------------------
# Les deux services HTTP. Ils renvoient leur nom ET les en-tetes que le proxy
# leur a transmis : c'est ce qui permet de prouver, cote backend, qu'un
# `mode http` a bien ajoute `X-Forwarded-For`, plutot que de croire un
# en-tete que le proxy aurait pu se declarer a lui-meme.
# ---------------------------------------------------------------------------
cat > "$WORK/service_http.py" <<'PY'
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        transmis = self.headers.get("X-Forwarded-For", "absent")
        hote = self.headers.get("Host", "absent")
        corps = (
            f"pub-haproxy-installation service {NOM}\n"
            f"chemin: {self.path}\n"
            f"host-recu: {hote}\n"
            f"x-forwarded-for: {transmis}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Service).serve_forever()
PY

# ---------------------------------------------------------------------------
# Le service de lignes. Il n'est pas un serveur HTTP : il repond a TOUTE
# ligne, y compris une ligne de requete HTTP, en la renvoyant prefixee. Un
# relais qui se contente de passer les octets le laisse donc repondre ; un
# proxy qui parle HTTP, lui, refuse la ligne avant meme de joindre un
# backend. Les deux comportements sont visibles depuis le client, et c'est la
# toute la demonstration.
# ---------------------------------------------------------------------------
cat > "$WORK/service_lignes.py" <<'PY'
import socketserver

PORT = 18121
PREFIXE = b"pub-haproxy-installation echo "


class Lignes(socketserver.StreamRequestHandler):
    timeout = 30

    def handle(self):
        while True:
            ligne = self.rfile.readline()
            if not ligne:
                return
            self.wfile.write(PREFIXE + ligne.strip() + b"\n")
            self.wfile.flush()


class Serveur(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


Serveur(("127.0.0.1", PORT), Lignes).serve_forever()
PY

chmod 0644 "$WORK/service_http.py" "$WORK/service_lignes.py"

poser_unite() {
    local nom="$1" description="$2" commande="$3"
    cat > "/etc/systemd/system/${nom}.service" <<UNIT
[Unit]
Description=${description}
After=network.target

[Service]
Type=simple
ExecStart=${commande}
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}

poser_unite pub-haproxy-installation-a \
    "HTTP service a for the HAProxy installation lab" \
    "/usr/bin/python3 ${WORK}/service_http.py a 18122"
poser_unite pub-haproxy-installation-b \
    "HTTP service b for the HAProxy installation lab" \
    "/usr/bin/python3 ${WORK}/service_http.py b 18123"
poser_unite pub-haproxy-installation-lignes \
    "Line protocol service for the HAProxy installation lab" \
    "/usr/bin/python3 ${WORK}/service_lignes.py"

systemctl daemon-reload
systemctl enable --now pub-haproxy-installation-a.service
systemctl enable --now pub-haproxy-installation-b.service
systemctl enable --now pub-haproxy-installation-lignes.service

for port in 18122 18123 18121; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

# ---------------------------------------------------------------------------
# La configuration de depart : un `global` et un `defaults`, et rien d'autre.
# La configuration livree par la distribution ecouterait et ferait passer une
# partie des controles sans travail.
# ---------------------------------------------------------------------------
install -d -m 0755 /etc/haproxy
cat > /etc/haproxy/haproxy.cfg <<'CFG'
# Point de depart du lab pub-haproxy-installation.
#
# Il n'y a volontairement AUCUN listener ici : ni `frontend`, ni `listen`.
# HAProxy refuse de demarrer sur une telle configuration, et le message qu'il
# rend est la premiere chose a savoir lire.
#
# Ce fichier ne declare pas non plus de socket d'administration. Le manifeste
# dit ce que la configuration doit presenter ; `man haproxy` et
# `/usr/share/doc/haproxy/` disent comment.
global
    log /dev/log local0
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon

defaults
    log     global
    option  dontlognull
    timeout connect 5s
    timeout client  30s
    timeout server  30s
CFG
chmod 0644 /etc/haproxy/haproxy.cfg

systemctl stop haproxy || true
systemctl disable haproxy || true

# Le paquet a demarre HAProxy a son installation, avec SA configuration, qui
# declare un socket d'administration. HAProxy ne retire pas son socket UNIX
# en s'arretant : le fichier survit au service, vide de tout processus
# derriere lui.
#
# Le laisser la ferait croire a un socket en service, et c'est exactement ce
# qui a fait echouer ce setup la premiere fois qu'il a tourne : le controle
# de precondition regardait la presence d'un FICHIER au lieu de l'existence
# d'un socket qui REPOND.
rm -f /run/haproxy/admin.sock

# ---------------------------------------------------------------------------
# Le manifeste. La version n'est PAS ecrite en dur : elle est relevee sur le
# binaire que le paquet vient d'installer. Un manifeste qui affirmerait
# « 2.8.5 » deviendrait faux au prochain correctif de securite de la
# distribution, et personne ne saurait dire si c'est le manifeste ou
# l'installation qui a tort.
#
# `nbthread` suit le nombre de processeurs de la machine, pour la meme
# raison : la valeur se mesure, elle ne se recopie pas.
# ---------------------------------------------------------------------------
# `sed -n '1s/...'` et non `haproxy -v | head -1` : `head` ferme le tube
# des la premiere ligne lue, `haproxy` prend un SIGPIPE a son ecriture
# suivante, et `set -o pipefail` fait echouer tout le pipeline. C'est une
# COURSE, gagnee au premier essai de ce lab et perdue au second.
#
# `sed` lit toute son entree avant de rendre la main : il n'y a plus de
# tube a fermer trop tot.
version_installee="$(/usr/sbin/haproxy -v 2>&1 \
    | sed -n '1s/.*version \([^ ]*\).*/\1/p')"
threads="$(nproc)"

cat > "$WORK/manifeste.txt" <<MANIFESTE
# Manifeste de pub-haproxy-installation.
#
# Chaque ligne « cle = valeur » est lue par la validation. Les lignes de
# commentaire, elles, ne le sont pas, et aucune ne commence par une des cles
# ci-dessous : un lecteur de mots-cles se laisse tromper par une phrase qui
# debute par le mot qu'il cherche.
#
# Ce que l'installation doit presenter :

version = ${version_installee}
maxconn = 2048
nbthread = ${threads}

# Les deux noms publies en HTTP sur le port 80, et le service que chacun doit
# atteindre :

nom_a = a.pub.lab.test
nom_b = b.pub.lab.test
service_a = 127.0.0.1:18122
service_b = 127.0.0.1:18123

# Le relais de connexion, en TCP, vers le service de lignes :

port_tcp = 7001
service_lignes = 127.0.0.1:18121

# La page d'etat, et le socket d'administration. Les deux doivent etre
# joignables depuis la machine, et depuis elle seule.

port_stats = 8404
socket_admin = /run/haproxy/admin.sock
MANIFESTE
chown student:student "$WORK/manifeste.txt"
chmod 0644 "$WORK/manifeste.txt"

# Le repertoire du socket d'administration. Le paquet ne le cree pas, et son
# absence est une des erreurs de demarrage les plus opaques de HAProxy.
install -d -m 0755 -o haproxy -g haproxy /run/haproxy

# `cmd && { ... }` serait un piege ici : sous `set -e`, une liste AND dont le
# premier membre echoue rend un statut non nul, et le script mourrait au
# moment meme ou le controle REUSSIT. On ecrit donc des `if`.
if systemctl is-active --quiet haproxy; then
    echo "haproxy ne devait pas tourner au sortir du setup"
    exit 1
fi
# On demande au socket s'il REPOND, au lieu de regarder si un fichier
# existe. Un fichier de socket survit au processus qui l'a cree : juger sur
# sa presence, c'est conclure sans avoir regarde ce qui compte.
if [ -S /run/haproxy/admin.sock ] \
    && echo | socat -t1 stdio /run/haproxy/admin.sock >/dev/null 2>&1; then
    echo "un socket d'administration repond deja au sortir du setup"
    exit 1
fi
echo "fixture pub-haproxy-installation posee"
exit 0
