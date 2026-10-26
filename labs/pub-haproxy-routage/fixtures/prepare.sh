#!/usr/bin/env bash
# Pose la situation : HAProxy en service, quatre backends sains, et une table
# de routage fausse.
#
# LES QUATRE FAUTES POSEES, toutes de la famille « ordre et ambiguite » :
#
#   1. la ligne de map est placee AVANT les exceptions de chemin, donc
#      aucune exception n'est jamais atteinte (premiere regle qui matche) ;
#   2. `path_beg /panier` attrape aussi `/panierarchive`, qui n'a rien a
#      voir : un prefixe n'est pas un chemin ;
#   3. `/api/v2/` est route vers l'API alors qu'il n'est pas deploye ;
#   4. `default_backend panier` : le panier devient la destination de tout
#      nom imprevu, y compris ceux qu'un tiers choisit.
#
# Aucune de ces quatre lignes n'est fausse EN ELLE-MEME. C'est leur ordre et
# leur portee qui decident, et ni l'un ni l'autre ne se lit dans la ligne
# qu'on regarde.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-routage.log) 2>&1
set -x

WORK=/opt/pub-haproxy-routage

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# ---------------------------------------------------------------------------
# Le backend. Un seul fichier, parametre par son nom et son port.
#
# `/__compteur` rend le nombre de requetes recues SANS s'y compter : un
# compteur qui s'incremente en se lisant ne mesure plus que sa propre
# consultation.
# ---------------------------------------------------------------------------
cat > "$WORK/service.py" <<'PY'
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])

_verrou = threading.Lock()
_recues = 0


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, corps):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        global _recues
        if self.path == "/__compteur":
            with _verrou:
                courant = _recues
            self._rendre(f"{courant}\n".encode())
            return
        with _verrou:
            _recues += 1
            courant = _recues
        hote = self.headers.get("Host", "absent")
        corps = (
            f"pub-haproxy-routage service {NOM}\n"
            f"chemin: {self.path}\n"
            f"host-recu: {hote}\n"
            f"requetes: {courant}\n"
        ).encode()
        self._rendre(corps)

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Service).serve_forever()
PY
chmod 0644 "$WORK/service.py"

poser_unite() {
    local nom="$1" port="$2"
    cat > "/etc/systemd/system/pub-haproxy-routage-${nom}.service" <<UNIT
[Unit]
Description=Backend ${nom} for the HAProxy routing lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/service.py ${nom} ${port}
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}

poser_unite vitrine 18131
poser_unite panier 18132
poser_unite console 18133
poser_unite api 18134

systemctl daemon-reload
for nom in vitrine panier console api; do
    systemctl enable --now "pub-haproxy-routage-${nom}.service"
done

for port in 18131 18132 18133 18134; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

# ---------------------------------------------------------------------------
# La map. Elle porte la route PAR DEFAUT de chaque nom ; les exceptions de
# chemin, elles, sont des regles. La map est volontairement correcte : ce
# n'est pas elle qui est fausse, c'est la place de la ligne qui la consulte.
# ---------------------------------------------------------------------------
install -d -m 0755 /etc/haproxy/maps
cat > /etc/haproxy/maps/noms.map <<'MAP'
# nom publie -> backend par defaut de ce nom
#
# Un nom absent de cette table n'a pas de route : la ligne qui consulte cette
# map doit donc nommer un defaut, et ce defaut doit refuser.
boutique.pub.lab.test vitrine
admin.pub.lab.test console
MAP
chmod 0644 /etc/haproxy/maps/noms.map

install -d -m 0755 /run/haproxy -o haproxy -g haproxy

cat > /etc/haproxy/haproxy.cfg <<'CFG'
global
    log /dev/log local0
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon
    maxconn 2048

    # Le socket est deja la : la mission de ce lab est le routage, pas
    # l'installation. C'est par lui que se fait un changement de table a
    # chaud, et c'est la seule voie autorisee pour en faire un.
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

    acl vise_panier path_beg /panier
    acl vise_api_v1 path_beg /api/v1/
    acl vise_api_v2 path_beg /api/v2/

    # FAUTE 1 : cette ligne est la premiere. HAProxy retient la premiere
    # regle qui matche, donc aucune des trois suivantes n'est jamais
    # atteinte. Elles sont pourtant ecrites, lisibles, et justes.
    use_backend %[req.hdr(host),lower,map(/etc/haproxy/maps/noms.map,refus)]

    # FAUTE 2 : `path_beg /panier` attrape `/panierarchive`. Un prefixe
    # n'est pas un chemin.
    use_backend panier if vise_panier

    use_backend api if vise_api_v1

    # FAUTE 3 : /api/v2/ n'est pas deploye. Le router vers l'API le fait
    # repondre comme s'il existait.
    use_backend api if vise_api_v2

    # FAUTE 4 : un nom imprevu atterrit sur le panier.
    default_backend panier

backend vitrine
    server vitrine 127.0.0.1:18131 check

backend panier
    server panier 127.0.0.1:18132 check

backend console
    server console 127.0.0.1:18133 check

backend api
    server api 127.0.0.1:18134 check

backend refus
    http-request deny deny_status 404

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

# ---------------------------------------------------------------------------
# La table que l'apprenant doit obtenir. Elle est ecrite comme une RECETTE,
# pas comme une configuration : elle dit ce qui doit arriver, jamais avec
# quelles directives l'obtenir.
# ---------------------------------------------------------------------------
cat > "$WORK/recette.txt" <<'RECETTE'
# Recette de routage de pub-haproxy-routage.
#
# Chaque ligne « attendu = <nom> <chemin> <backend> » est lue par la
# validation. `refus` signifie : la requete ne doit atteindre AUCUN backend,
# et HAProxy doit repondre 403 ou 404.
#
# Les chemins voisins sont dans cette table a dessein : c'est la qu'un
# prefixe se fait passer pour un chemin.

attendu = boutique.pub.lab.test / vitrine
attendu = boutique.pub.lab.test /catalogue vitrine
attendu = boutique.pub.lab.test /panier panier
attendu = boutique.pub.lab.test /panier/ajouter panier
attendu = boutique.pub.lab.test /panierarchive vitrine
attendu = boutique.pub.lab.test /panier-public vitrine
attendu = admin.pub.lab.test / console
attendu = admin.pub.lab.test /api/v1/etat api
attendu = admin.pub.lab.test /api/v1/ api
attendu = admin.pub.lab.test /api/v2/etat refus
attendu = admin.pub.lab.test /panier console

# Chaque backend compte ses requetes, et le dit sur sa boucle locale. C'est
# par la que la validation sait quel backend a REELLEMENT ete joint : une
# route qui fuit rend une reponse plausible, et seul le backend peut dire
# qu'il l'a servie.

compteur = vitrine 18131
compteur = panier 18132
compteur = console 18133
compteur = api 18134

# La table des noms, et la voie autorisee pour la changer a chaud :

map_noms = /etc/haproxy/maps/noms.map
socket_admin = /run/haproxy/admin.sock

# Le dossier a rendre, relu par un humain :

dossier = /opt/pub-haproxy-routage/dossier.md
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

# Le constat de depart, pour que l'apprenant voie l'etat qu'il doit changer
# sans avoir a le deviner.
echo "--- etat de depart, depuis la machine ---"
for essai in "boutique.pub.lab.test /" "boutique.pub.lab.test /panierarchive" \
             "admin.pub.lab.test /api/v2/etat" "inconnu.lab.test /"; do
    set -- $essai
    echo "## Host: $1  chemin: $2"
    curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 \
        -H "Host: $1" "http://127.0.0.1$2" || true
done

echo "fixture pub-haproxy-routage posee"
exit 0
