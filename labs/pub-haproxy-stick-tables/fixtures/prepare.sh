#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-stick-tables.log) 2>&1
set -x

WORK=/opt/pub-haproxy-stick-tables

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

cat > "$WORK/service.py" <<'PY'
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 18171
_verrou = threading.Lock()
_recues = 0


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, statut, corps):
        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        global _recues
        if self.path == "/__compteur":
            with _verrou:
                courant = _recues
            self._rendre(200, f"{courant}\n".encode())
            return
        with _verrou:
            _recues += 1
            courant = _recues
        corps = (
            "pub-haproxy-stick-tables service\n"
            f"chemin: {self.path}\n"
            f"requetes: {courant}\n"
        ).encode()
        self._rendre(200, corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Service).serve_forever()
PY
chmod 0644 "$WORK/service.py"

cat > /etc/systemd/system/pub-haproxy-stick-tables-service.service <<UNIT
[Unit]
Description=Backend for the HAProxy stick-table lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/service.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now pub-haproxy-stick-tables-service.service
for _ in $(seq 60); do
    if ss -ltn 'sport = :18171' | grep -q LISTEN; then break; fi
    sleep 1
done

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-stick-tables.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-stick-tables.conf

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
    timeout client  30s
    timeout server  30s

frontend public
    bind :80

    # FAUTE 1 : la cle suivie est un en-tete que le CLIENT envoie. Chacun
    # choisit donc son propre compteur, et il suffit d'en changer pour
    # repartir de zero. La table se remplit, se lit, et ne protege de rien.
    http-request track-sc0 req.hdr(X-Client-Id) table compteurs

    # FAUTE 2 : un seuil qu'aucun trafic realiste n'atteint. La regle existe,
    # elle est juste, et elle ne se declenche jamais.
    http-request deny deny_status 429 if { sc_http_req_rate(0) gt 10000 }

    default_backend applicatif

# La table vit dans un backend qui ne sert rien d'autre, et c'est la forme
# attendue : `stick-table` ne se declare pas dans un `frontend`. Lui donner
# son propre backend la NOMME, ce qui permet de la lire par
# `show table compteurs` et de la partager entre plusieurs frontends.
backend compteurs
    # FAUTE 3 : `expire` et la fenetre de `http_req_rate` sont confondues en
    # une seule valeur courte. Ce sont deux bornes differentes : l'une dit
    # sur combien de temps la cadence est mesuree, l'autre combien de temps
    # l'entree survit a sa derniere requete.
    #
    # FAUTE 1, son autre moitie : `type string`. Une table de chaines ne peut
    # pas etre clavee sur une adresse ; changer la cle sans changer le type
    # ne charge pas.
    stick-table type string len 64 size 100 expire 10s store http_req_rate(10s)

backend applicatif
    server app 127.0.0.1:18171 check

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
# Recette de pub-haproxy-stick-tables.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# CE QUE LA TABLE DOIT COMPTER, ET SUR QUOI
#
# L'objet compte est l'ADRESSE DU CLIENT, et non une valeur qu'il fournit.
# Un client qui peut choisir sa cle peut choisir son compteur.

objet = adresse-source
table = compteurs

# LES DEUX BORNES DE TEMPS, qui ne disent pas la meme chose et que la
# validation mesure separement :
#
#   fenetre      sur combien de secondes la cadence est mesuree ;
#   expiration   combien de secondes une entree survit a sa derniere requete.

fenetre = 10
expiration = 30

# LE SEUIL. Une rafale de `seuil` requetes dans la fenetre doit PASSER ; au
# dela, le refus est un 429. La borne est inclusive : un controle qui
# refuserait a `seuil` serait plus strict que ce qui est demande.

seuil = 20
statut_refus = 429

# LA TAILLE de la table, en nombre d'entrees.

taille = 100

# LE DOSSIER a rendre, relu par un humain. Il doit dire ce que cette table ne
# protege PAS.

dossier = /opt/pub-haproxy-stick-tables/dossier.md

socket_admin = /run/haproxy/admin.sock
compteur_backend = 127.0.0.1:18171
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "--- etat de depart : la cle se choisit, donc le compteur se choisit ---"
for valeur in un deux trois; do
    curl -s -o /dev/null -w "%{http_code} " --max-time 5 \
        -H "X-Client-Id: $valeur" http://127.0.0.1/ || true
done
echo
echo 'show table' | socat -t2 stdio /run/haproxy/admin.sock || true

echo "fixture pub-haproxy-stick-tables posee"
exit 0
