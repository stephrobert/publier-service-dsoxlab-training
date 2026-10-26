#!/usr/bin/env bash
# Pose la situation : la generation 1.4.2 en service, la 1.5.0 disponible et
# arretee, et AUCUN moyen de passer de l'une a l'autre.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-mise-a-jour.log) 2>&1
set -x

WORK=/opt/pub-haproxy-mise-a-jour

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# ---------------------------------------------------------------------------
# Le gabarit d'application. Chaque generation est un fichier distinct ou la
# version est FIGEE : une application qui lirait sa version dans un fichier
# de configuration ne prouverait pas qu'on a bien change de binaire.
# ---------------------------------------------------------------------------
cat > "$WORK/gabarit.py" <<'PY'
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "@VERSION@"
PORT = @PORT@


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, statut, corps):
        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if self.path == "/pret":
            self._rendre(200, b"pret\n")
            return
        if self.path.startswith("/flux"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(f"flux ouvert par {VERSION}\n".encode())
            self.wfile.flush()
            # 45 secondes, et non 90. `dsoxlab check` borne pytest a 300 s
            # pour TOUTE la suite, et ce lab redemarre en plus la machine :
            # mesure du 2026-10-26, la suite depassait et le verdict sortait
            # en SKIP sans que rien soit mesure. Quarante-cinq secondes
            # couvrent largement une bascule, qui est ce que le flux doit
            # traverser : ce qu'il prouve ne depend pas de sa duree, mais du
            # fait qu'il soit ETABLI AVANT la bascule et VIVANT APRES.
            for numero in range(45):
                time.sleep(1)
                try:
                    self.wfile.write(f"ligne {numero} {VERSION}\n".encode())
                    self.wfile.flush()
                except OSError:
                    return
            self.close_connection = True
            return
        self._rendre(
            200,
            f"pub-haproxy-mise-a-jour version {VERSION}\n"
            f"chemin: {self.path}\n".encode(),
        )

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Service).serve_forever()
PY

poser_generation() {
    local version="$1" port="$2"
    sed -e "s/@VERSION@/${version}/g" -e "s/@PORT@/${port}/g" \
        "$WORK/gabarit.py" > "$WORK/application-${version}.py"
    chmod 0644 "$WORK/application-${version}.py"
}

poser_generation 1.4.2 18211
poser_generation 1.5.0 18212

# UNE unite modele, et une instance par generation. `%i` porte la version :
# il n'y a donc rien a editer pour en ajouter une, et c'est ce qui rend une
# livraison repetable.
cat > /etc/systemd/system/pub-maj-app@.service <<UNIT
[Unit]
Description=Application generation %i for the HAProxy update lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/application-%i.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now 'pub-maj-app@1.4.2.service'
for _ in $(seq 60); do
    if ss -ltn 'sport = :18211' | grep -q LISTEN; then break; fi
    sleep 1
done

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-mise-a-jour.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-mise-a-jour.conf

# Le fichier que la livraison reecrira. Il est inclus par la configuration
# principale : une livraison ne touche ainsi qu'une ligne, et le reste de la
# configuration n'est jamais en jeu.
install -d -m 0755 /etc/haproxy/service.d
cat > /etc/haproxy/service.d/generation.cfg <<'GEN'
backend applicatif
    option httpchk GET /pret
    http-check expect status 200
    server courante 127.0.0.1:18211 check inter 1s fall 3 rise 2
GEN
chmod 0644 /etc/haproxy/service.d/generation.cfg

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
    timeout client  180s
    timeout server  180s

frontend public
    bind :80
    default_backend applicatif

listen etat
    bind 127.0.0.1:8404
    stats enable
    stats uri /
CFG
# `-f` deux fois : HAProxy lit les fichiers dans l'ordre donne. L'unite du
# paquet n'en passe qu'un, donc le second est ajoute par une surcharge.
install -d -m 0755 /etc/systemd/system/haproxy.service.d
cat > /etc/systemd/system/haproxy.service.d/generation.conf <<'DROPIN'
[Service]
Environment="EXTRAOPTS=-S /run/haproxy-master.sock -f /etc/haproxy/service.d/generation.cfg"
DROPIN
chmod 0644 /etc/haproxy/haproxy.cfg /etc/systemd/system/haproxy.service.d/generation.conf

systemctl daemon-reload
haproxy -c -f /etc/haproxy/haproxy.cfg -f /etc/haproxy/service.d/generation.cfg
systemctl enable haproxy
systemctl restart haproxy
for _ in $(seq 60); do
    if ss -ltn 'sport = :80' | grep -q LISTEN; then break; fi
    sleep 1
done

cat > "$WORK/manifeste.txt" <<'MANIFESTE'
# Manifeste de pub-haproxy-mise-a-jour.
#
# Deux generations de l'application. Chacune FIGE sa version dans son
# fichier : une application qui lirait sa version ailleurs ne prouverait pas
# qu'on a bien change de code.
#
# Aucune ligne de prose ci-dessous ne commence par un des mots-cles lus par
# la validation : un lecteur de mots-cles se laisse tromper par une phrase
# qui debute par le mot qu'il cherche.

generation = 1.4.2 18211
generation = 1.5.0 18212

# La generation en service au depart :

depart = 1.4.2

# Le fichier que la livraison reecrit, et lui seul. Toucher une seule ligne
# rend la livraison relisable, et le retour aussi.

fichier_generation = /etc/haproxy/service.d/generation.cfg

# Les deux executables a livrer. La validation les EXECUTE : une bascule ne
# se constate pas apres coup, elle se joue.

livrer = /opt/pub-haproxy-mise-a-jour/livrer
revenir = /opt/pub-haproxy-mise-a-jour/revenir
journal = /opt/pub-haproxy-mise-a-jour/journal.md

socket_admin = /run/haproxy/admin.sock
backend = applicatif
MANIFESTE
chown student:student "$WORK/manifeste.txt"
chmod 0644 "$WORK/manifeste.txt"

cat > "$WORK/plan.txt" <<'PLAN'
Plan de mise a jour de pub-haproxy-mise-a-jour.

CE QUE VOUS LIVREZ

  livrer <version>   met la generation demandee en service
  revenir            revient a la generation precedente

Les deux sont des executables. Le langage est libre. La validation les
appelle, elle ne les lit pas.

LES QUATRE ETAPES QUE LA VALIDATION JOUE

  1. elle constate la generation de depart ;
  2. elle ouvre un flux long et une sonde continue, puis appelle
     `livrer 1.5.0` et mesure pendant la bascule ;
  3. elle appelle `revenir` et refait la meme mesure ;
  4. elle redemarre la machine et rejoue la recette.

LE CONTRAT DE DISPONIBILITE

  - au plus UNE requete courte en echec pendant une bascule ;
  - un flux long ouvert AVANT la bascule doit continuer de recevoir APRES,
    et aller jusqu'a son terme ;
  - le processus MAITRE de HAProxy ne doit pas changer pendant une bascule.
    C'est lui qui tient les sockets d'ecoute : le remplacer ferme le port,
    et aucune mesure cote client ne le rattrape.

POURQUOI LA GENERATION PRECEDENTE RESTE EN VIE

Un rechargement de HAProxy demarre de nouveaux ouvriers et laisse les
anciens finir les connexions qu'ils tiennent. Ces anciens ouvriers parlent
encore a la generation d'application qu'ils connaissaient : l'arreter
immediatement couperait les flux qu'ils servent.

Une livraison ne retire donc pas la generation qu'elle remplace. Elle retire
celle qui avait ete remplacee a la livraison PRECEDENTE.

LE JOURNAL

Un `journal.md` dit ce qui a ete fait, ce qui a ete mesure pendant la
bascule, et comment revenir. Il est relu par un humain.
PLAN
chown student:student "$WORK/plan.txt"
chmod 0644 "$WORK/plan.txt"
chown -R student:student "$WORK"

echo "--- etat de depart ---"
curl -s --max-time 10 http://127.0.0.1/ || true
echo "maitre : $(systemctl show -p MainPID --value haproxy)"
pgrep -P "$(systemctl show -p MainPID --value haproxy)" || true

echo "fixture pub-haproxy-mise-a-jour posee"
exit 0
