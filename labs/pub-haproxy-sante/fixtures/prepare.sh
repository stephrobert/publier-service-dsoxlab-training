#!/usr/bin/env bash
# Pose la situation : deux backends pilotables, et un HAProxy sans sondes.
#
# CE QUE LE SETUP NE FAIT PAS : il ne declare ni `option httpchk`, ni `check`,
# ni poids. Les deux serveurs sont a poids egaux et personne ne les surveille.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-sante.log) 2>&1
set -x

WORK=/opt/pub-haproxy-sante

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

cat > "$WORK/service.py" <<'PY'
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])
ETAT = pathlib.Path(sys.argv[3])

_verrou = threading.Lock()
_recues = 0


def _pret():
    # L'etat est relu A CHAQUE REQUETE, et non garde en memoire : le test
    # bascule le fichier et attend que le service suive sans redemarrer.
    try:
        return ETAT.read_text().strip() == "pret"
    except OSError:
        return True


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, statut, corps):
        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _lent(self):
        # Un flux long, volontairement indifferent a l'etat de sante : le
        # drainage se mesure sur une connexion etablie, et melanger les deux
        # rendrait le resultat illisible.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(f"pub-haproxy-sante service {NOM}\n".encode())
        self.wfile.flush()
        for numero in range(20):
            time.sleep(1)
            try:
                self.wfile.write(f"ligne {numero}\n".encode())
                self.wfile.flush()
            except OSError:
                return
        self.close_connection = True

    def do_GET(self):
        global _recues
        if self.path == "/__compteur":
            with _verrou:
                courant = _recues
            self._rendre(200, f"{courant}\n".encode())
            return
        if self.path == "/ready":
            if _pret():
                self._rendre(200, b"pret\n")
            else:
                self._rendre(503, b"casse\n")
            return
        if self.path.startswith("/lent"):
            self._lent()
            return

        with _verrou:
            _recues += 1
            courant = _recues
        if not _pret():
            self._rendre(
                500,
                f"pub-haproxy-sante service {NOM} en echec\n".encode(),
            )
            return
        corps = (
            f"pub-haproxy-sante service {NOM}\n"
            f"chemin: {self.path}\n"
            f"requetes: {courant}\n"
        ).encode()
        self._rendre(200, corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Service).serve_forever()
PY
chmod 0644 "$WORK/service.py"

# Les deux fichiers d'etat. Ils appartiennent a student : l'apprenant doit
# pouvoir provoquer la panne lui-meme pour voir sa configuration reagir.
for nom in alpha beta; do
    echo pret > "$WORK/etat-${nom}"
    chown student:student "$WORK/etat-${nom}"
    chmod 0664 "$WORK/etat-${nom}"
done

poser_unite() {
    local nom="$1" port="$2"
    cat > "/etc/systemd/system/pub-haproxy-sante-${nom}.service" <<UNIT
[Unit]
Description=Backend ${nom} for the HAProxy health lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/service.py ${nom} ${port} ${WORK}/etat-${nom}
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}

poser_unite alpha 18141
poser_unite beta 18142

systemctl daemon-reload
systemctl enable --now pub-haproxy-sante-alpha.service
systemctl enable --now pub-haproxy-sante-beta.service

for port in 18141 18142; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

install -d -m 0755 -o haproxy -g haproxy /run/haproxy

cat > /etc/haproxy/haproxy.cfg <<'CFG'
global
    log /dev/log local0
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon
    maxconn 2048
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s

defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    timeout connect 5s
    timeout client  60s
    timeout server  60s

frontend public
    bind :80
    default_backend applicatif

# ETAT DE DEPART : deux serveurs, a poids egaux, et PERSONNE ne les
# surveille. Pas de `option httpchk`, pas de `check`, pas de `weight`.
#
# Consequence, et c'est ce qu'il faut constater avant d'ecrire quoi que ce
# soit : un backend qui tombe reste dans la rotation, et une requete sur deux
# part chez lui.
backend applicatif
    balance roundrobin
    server alpha 127.0.0.1:18141
    server beta  127.0.0.1:18142

listen etat
    bind 127.0.0.1:8404
    stats enable
    stats uri /
CFG
chmod 0644 /etc/haproxy/haproxy.cfg

haproxy -c -f /etc/haproxy/haproxy.cfg
systemctl enable haproxy
systemctl restart haproxy

for _ in $(seq 60); do
    if ss -ltn 'sport = :80' | grep -q LISTEN; then break; fi
    sleep 1
done

cat > "$WORK/recette.txt" <<'RECETTE'
# Recette de pub-haproxy-sante.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# LES POIDS, en etat sain. Sur un echantillon, chaque serveur doit prendre
# la part que son poids lui donne.

poids = alpha 3
poids = beta 1

# LES SEUILS DE LA SONDE. Ils sont prescrits, et non laisses au choix,
# parce que la validation mesure des FENETRES : un retrait doit avoir lieu,
# et une panne plus courte que le seuil ne doit PAS en provoquer.

sonde = /ready
inter = 1
fall = 5
rise = 3

# Ou piloter l'etat de chaque backend, et par ou passer pour agir a chaud :

etat = alpha /opt/pub-haproxy-sante/etat-alpha
etat = beta /opt/pub-haproxy-sante/etat-beta
compteur = alpha 18141
compteur = beta 18142
backend = applicatif
socket_admin = /run/haproxy/admin.sock
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "--- etat de depart : une requete sur deux part chez un backend casse ---"
echo casse > "$WORK/etat-beta"
sleep 1
for _ in $(seq 6); do
    curl -s -o /dev/null -w '%{http_code} ' --max-time 5 http://127.0.0.1/ || true
done
echo
echo pret > "$WORK/etat-beta"
chown student:student "$WORK/etat-beta"

echo "fixture pub-haproxy-sante posee"
exit 0
