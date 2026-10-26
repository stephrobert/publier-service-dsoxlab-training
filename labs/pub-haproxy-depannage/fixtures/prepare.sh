#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-depannage.log) 2>&1
set -x

WORK=/opt/pub-haproxy-depannage
PKI="$WORK/pki"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat openssl

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0755 -o student -g student "$PKI"

creer_ca() {
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout "$PKI/$1.key" -out "$PKI/$1.crt" -subj "/CN=$2" 2>/dev/null
}
signer() {
    local ca="$1" nom="$2" cn="$3"
    openssl req -newkey rsa:2048 -nodes -keyout "$PKI/$nom.key" \
        -out "$PKI/$nom.csr" -subj "/CN=$cn" \
        -addext "subjectAltName=DNS:$cn" 2>/dev/null
    openssl x509 -req -in "$PKI/$nom.csr" -CA "$PKI/$ca.crt" \
        -CAkey "$PKI/$ca.key" -out "$PKI/$nom.crt" -days 365 \
        -copy_extensions copy 2>/dev/null
    rm -f "$PKI/$nom.csr"
}

creer_ca ca-backend "AC des backends du lab"
creer_ca ca-etrangere "AC etrangere du lab"
signer ca-backend api "api-interne.lab"
signer ca-etrangere imposteur "api-interne.lab"
chown -R student:student "$PKI"
chmod 0644 "$PKI"/*.crt
chmod 0640 "$PKI"/*.key

# ---------------------------------------------------------------------------
# Quatre services. `sonde-cassee` est sain au niveau TCP et DEGRADE au niveau
# applicatif : sa readiness echoue et ses routes utiles rendent 500. C'est la
# panne qu'une sonde existe pour voir, et le canari qui interdit de retirer
# les sondes.
# ---------------------------------------------------------------------------
cat > "$WORK/service.py" <<'PY'
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])
DEGRADE = sys.argv[3] == "degrade"
CERT = sys.argv[4] if len(sys.argv) > 4 else ""
CLE = sys.argv[5] if len(sys.argv) > 5 else ""


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, statut, corps):
        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if self.path.startswith("/bloque"):
            # Occupe une place et ne la rend pas. C'est ce qu'un client
            # coince fait dans la vraie vie, et c'est la seule facon de
            # rendre une saturation reproductible.
            import time

            time.sleep(3600)
            self._rendre(200, b"fini\n")
            return
        if self.path.startswith("/ready"):
            if DEGRADE:
                self._rendre(503, b"pas pret\n")
            else:
                self._rendre(200, b"pret\n")
            return
        if DEGRADE:
            self._rendre(500, f"pub-haproxy-depannage {NOM} en echec\n".encode())
            return
        self._rendre(
            200,
            f"pub-haproxy-depannage service {NOM}\nchemin: {self.path}\n".encode(),
        )

    def log_message(self, *args):
        return


serveur = ThreadingHTTPServer(("127.0.0.1", PORT), Service)
if CERT:
    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte.load_cert_chain(CERT, CLE)
    serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
serveur.serve_forever()
PY
chmod 0644 "$WORK/service.py"

poser_unite() {
    local nom="$1" args="$2"
    cat > "/etc/systemd/system/pub-haproxy-depannage-${nom}.service" <<UNIT
[Unit]
Description=Backend ${nom} for the HAProxy troubleshooting lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/service.py ${args}
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}

poser_unite app "app 18202 sain"
poser_unite sonde-cassee "sonde-cassee 18203 degrade"
poser_unite api "api 18201 sain ${PKI}/api.crt ${PKI}/api.key"
poser_unite imposteur "api 18204 sain ${PKI}/imposteur.crt ${PKI}/imposteur.key"

systemctl daemon-reload
for nom in app sonde-cassee api imposteur; do
    systemctl enable --now "pub-haproxy-depannage-${nom}.service"
done
for port in 18201 18202 18203 18204; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

grep -q 'dsoxlab-pub-haproxy-depannage' /etc/hosts \
    || echo "127.0.0.1 api-interne.lab # dsoxlab-pub-haproxy-depannage" >> /etc/hosts

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-depannage.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-depannage.conf

# ---------------------------------------------------------------------------
# LA PILE SAINE. Elle est ecrite une fois, et la variante l'abime ensuite.
# ---------------------------------------------------------------------------
ecrire_pile_saine() {
cat > /etc/haproxy/haproxy.cfg <<CFG
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
    timeout queue   10s
    timeout client  30s
    timeout server  30s

# Du BRUIT : un nom abandonne qui ne sert plus rien. Present dans toutes les
# variantes, cause d'aucune.
frontend ancien
    bind 127.0.0.1:8081
    http-request deny deny_status 404

backend compteurs
    stick-table type ip size 100 expire 60s store http_req_rate(10s)

frontend public
    bind :80

    http-request track-sc0 src table compteurs
    http-request deny deny_status 429 if { sc_http_req_rate(0) gt 200 }

    acl est_api        path_beg /api/
    acl est_api_usurpe path_beg /api-usurpe/

    use_backend api_usurpe if est_api_usurpe
    use_backend api        if est_api
    default_backend applicatif

backend applicatif
    balance roundrobin
    option httpchk GET /ready
    http-check expect status 200
    server app 127.0.0.1:18202 check inter 1s fall 3 rise 2
    # LE CANARI DES SONDES. Il est vivant, sa readiness echoue, et ses
    # routes utiles rendent 500. Il doit rester hors service.
    server sonde-cassee 127.0.0.1:18203 check inter 1s fall 3 rise 2

backend api
    option httpchk GET /ready
    http-check expect status 200
    server api api-interne.lab:18201 check inter 1s fall 3 rise 2 ssl verify required ca-file ${PKI}/ca-backend.crt verifyhost api-interne.lab

# LE CANARI DE LA CONFIANCE. Meme nom, autre autorite, meme marqueur : si la
# verification est desactivee, sa reponse est indiscernable d'un succes.
backend api_usurpe
    server imposteur 127.0.0.1:18204 ssl verify required ca-file ${PKI}/ca-backend.crt verifyhost api-interne.lab

listen etat
    bind 127.0.0.1:8404
    stats enable
    stats uri /
CFG
chmod 0644 /etc/haproxy/haproxy.cfg
}

ecrire_pile_saine
haproxy -c -f /etc/haproxy/haproxy.cfg
systemctl enable haproxy
systemctl restart haproxy
for _ in $(seq 60); do
    if ss -ltn 'sport = :80' | grep -q LISTEN; then break; fi
    sleep 1
done

# ---------------------------------------------------------------------------
# LA VARIANTE. Tiree au hasard, notee sur le disque pour la seule relecture
# humaine, et JAMAIS lue par le corrige de reference.
# ---------------------------------------------------------------------------
VARIANTE="$(printf 'routage\nsonde\ntls\nlimite\nsaturation\n' | shuf -n 1)"
echo "$VARIANTE" > /root/.variante-pub-haproxy-depannage
chmod 0600 /root/.variante-pub-haproxy-depannage

case "$VARIANTE" in
routage)
    # Une expression reguliere l'emporte sur un prefixe : la route /api/
    # devient inatteignable, et le trafic part sur l'applicatif.
    sed -i 's|    use_backend api        if est_api|    use_backend applicatif if { path_reg ^/api }\n    use_backend api        if est_api|' \
        /etc/haproxy/haproxy.cfg
    ;;
sonde)
    # La sonde interroge un chemin qui n'existe pas : TOUS les serveurs
    # tombent, y compris les sains.
    sed -i 's|option httpchk GET /ready|option httpchk GET /etat-du-service|g' \
        /etc/haproxy/haproxy.cfg
    ;;
tls)
    # Le magasin de confiance du proxy est remplace par l'autorite
    # etrangere : le backend legitime devient un imposteur a ses yeux.
    cp "$PKI/ca-etrangere.crt" "$PKI/ca-backend.crt"
    ;;
limite)
    # Un seuil de une requete par fenetre : tout le trafic est refuse.
    sed -i 's|sc_http_req_rate(0) gt 200|sc_http_req_rate(0) gt 1|' \
        /etc/haproxy/haproxy.cfg
    ;;
saturation)
    # Une seule connexion a la fois vers le serveur sain, aucune borne de
    # file, et un client coince qui occupe cette unique place. Les requetes
    # suivantes attendent, puis echouent.
    #
    # La ventouse n'est pas un artifice : c'est exactement ce qui sature un
    # service en production, un appel qui ne rend jamais la main. Sans elle,
    # `maxconn 1` ne casserait rien sous une requete a la fois, et le lab
    # n'aurait aucune panne a diagnostiquer.
    sed -i 's|    server app 127.0.0.1:18202 check|    server app 127.0.0.1:18202 maxconn 1 check|' \
        /etc/haproxy/haproxy.cfg
    sed -i '/timeout queue   10s/d' /etc/haproxy/haproxy.cfg
    cat > /etc/systemd/system/pub-haproxy-depannage-ventouse.service <<'UNIT'
[Unit]
Description=A client that holds a slot and never gives it back
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/curl -s --max-time 3000 http://127.0.0.1/bloque
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
    systemctl enable --now pub-haproxy-depannage-ventouse.service
    ;;
esac

# Du bruit de configuration, pose APRES la variante et cause d'aucune panne.
cat > /etc/haproxy/notes-exploitation.txt <<'NOTES'
# Notes d'exploitation, laissees par l'equipe precedente.
#
# - la route /api-usurpe/ est une sonde de confiance, elle DOIT repondre 502
#   ou 503. Ne pas la retirer.
# - le frontend `ancien` n'est plus utilise depuis la migration.
# - le serveur `sonde-cassee` est une machine en panne, laissee declaree
#   exprès : elle doit rester hors service.
NOTES

if [ "$VARIANTE" = saturation ]; then
    # On relance la ventouse apres le rechargement : partie avant, elle
    # aurait pris sa place sous l'ancienne configuration, qui n'avait pas
    # de limite, et la saturation ne se produirait pas.
    systemctl restart pub-haproxy-depannage-ventouse.service || true
fi

if haproxy -c -f /etc/haproxy/haproxy.cfg 2>/dev/null; then
    systemctl reload haproxy || systemctl restart haproxy
else
    # Une variante peut rendre la configuration incorrecte : c'est un cas
    # legitime, et le service reste alors a terre.
    systemctl restart haproxy || true
fi
sleep 3

cat > "$WORK/recette.txt" <<RECETTE
# Recette de pub-haproxy-depannage.
#
# Elle decrit l'etat SAIN attendu. Une panne a ete injectee : a vous de la
# trouver, et de revenir a cet etat.
#
# LA MATRICE A REJOUER, « attendu = <chemin> <marqueur ou code> » :

attendu = / app
attendu = /quoi-que-ce-soit app
attendu = /api/ api
attendu = /api/etat api

# LES DEUX CANARIS. Ils font partie de l'etat SAIN, pas de la panne, et ils
# doivent le rester : ce sont eux qui prouvent que la correction n'a pas
# consiste a desactiver une verification.

canari_tls = /api-usurpe/
canari_sonde = sonde-cassee

# CE QUI NE DOIT PAS ETRE JOIGNABLE DEPUIS LE RESEAU :

port_stats = 8404
ports_backends = 18201 18202 18203 18204
socket_admin = /run/haproxy/admin.sock
backend_applicatif = applicatif

# LE DOSSIER DE DIAGNOSTIC, relu par un humain.

dossier = ${WORK}/diagnostic.md
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "--- etat apres injection ---"
for chemin in / /api/ /api-usurpe/; do
    echo -n "$chemin : "
    curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 \
        "http://127.0.0.1$chemin" || echo "pas de reponse"
done

# La variante doit avoir casse quelque chose. Si tout repond encore, le lab
# ne presente aucune panne a diagnostiquer, et il vaut mieux le dire ici que
# laisser l'apprenant chercher ce qui n'existe pas.
accueil="$(curl -s --max-time 10 http://127.0.0.1/ || true)"
api="$(curl -s --max-time 10 http://127.0.0.1/api/ || true)"
if [[ "$accueil" == *"service app"* && "$api" == *"service api"* ]]; then
    echo "l'injection ($VARIANTE) n'a rien casse : il n'y a rien a diagnostiquer" >&2
    exit 1
fi

echo "fixture pub-haproxy-depannage posee (variante cachee)"
exit 0
