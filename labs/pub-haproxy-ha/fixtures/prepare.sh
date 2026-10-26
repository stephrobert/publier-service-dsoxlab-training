#!/usr/bin/env bash
# Pose un point d'entree complet : application, TLS, politique d'acces.
# Et keepalived installe, NON configure.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-ha.log) 2>&1
set -x

WORK=/opt/pub-haproxy-ha
PKI="$WORK/pki"
MOI="$(hostname -s)"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends keepalived curl socat openssl

install -d -m 0775 -o student -g student "$WORK"
install -d -m 0755 -o student -g student "$PKI"

# ---------------------------------------------------------------------------
# LA PKI. Generee sur le premier point d'entree, RECUE sur le second : les
# deux doivent presenter le meme certificat. Un client qui verifie
# strictement verra sinon un service different selon qui repond, et la
# bascule deviendrait visible la ou elle doit etre invisible.
# ---------------------------------------------------------------------------
if [ "${PKI_FOURNIE:-0}" = 1 ]; then
    test -f "$PKI/ca.crt" || { echo "PKI annoncee fournie, et absente" >&2; exit 1; }
    test -f "$PKI/service.pem" || { echo "le PEM de service est absent" >&2; exit 1; }
else
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout "$PKI/ca.key" -out "$PKI/ca.crt" \
        -subj "/CN=AC du lab de haute disponibilite" 2>/dev/null
    openssl req -newkey rsa:2048 -nodes -keyout "$PKI/service.key" \
        -out "$PKI/service.csr" -subj "/CN=service.pub.lab.test" \
        -addext "subjectAltName=DNS:service.pub.lab.test" 2>/dev/null
    openssl x509 -req -in "$PKI/service.csr" -CA "$PKI/ca.crt" \
        -CAkey "$PKI/ca.key" -out "$PKI/service.crt" -days 365 \
        -copy_extensions copy 2>/dev/null
    rm -f "$PKI/service.csr"
    cat "$PKI/service.key" "$PKI/service.crt" > "$PKI/service.pem"
fi
chown -R student:student "$PKI"
chmod 0644 "$PKI"/*.crt "$PKI/service.pem" 2>/dev/null || true
chmod 0640 "$PKI"/*.key 2>/dev/null || true

# ---------------------------------------------------------------------------
# L'application. Elle annonce LA MACHINE qui la sert : c'est par elle que la
# validation sait quel point d'entree a repondu, et aucune autre source ne
# peut le dire une fois l'adresse flottante en place.
# ---------------------------------------------------------------------------
cat > "$WORK/service.py" <<'PY'
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 18221
MACHINE = socket.gethostname().split(".")[0]


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        corps = (
            f"pub-haproxy-ha service {MACHINE}\n"
            f"chemin: {self.path}\n"
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
chmod 0644 "$WORK/service.py"

cat > /etc/systemd/system/pub-haproxy-ha-service.service <<UNIT
[Unit]
Description=Application behind the HAProxy high-availability lab
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
systemctl enable --now pub-haproxy-ha-service.service
for _ in $(seq 60); do
    if ss -ltn 'sport = :18221' | grep -q LISTEN; then break; fi
    sleep 1
done

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-ha.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-ha.conf

# ---------------------------------------------------------------------------
# Le point d'entree. IDENTIQUE sur les deux machines : c'est ce que le
# controle de coherence verifie, et c'est ce qui rend une bascule invisible.
#
# `bind :443` et non une adresse precise : une ecoute sur une adresse qui
# n'existe pas encore refuserait de demarrer, et l'adresse flottante
# n'existe sur aucune des deux machines au repos. C'est le piege le plus
# commun de cette famille, et il est evite ici pour que l'apprenant travaille
# sur la bascule, pas sur un service qui ne demarre pas.
# ---------------------------------------------------------------------------
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
    ssl-default-bind-options ssl-min-ver TLSv1.2

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
    bind :443 ssl crt ${PKI}/service.pem

    http-request redirect scheme https code 308 unless { ssl_fc }

    # La politique d'acces, identique des deux cotes. Elle doit tenir APRES
    # une bascule : une politique qui ne suit pas le service est une
    # ouverture qui s'ignore.
    acl est_prive path_beg /prive/
    acl depuis_la_machine src 127.0.0.0/8
    http-request deny deny_status 403 if est_prive !depuis_la_machine

    default_backend applicatif

backend applicatif
    option httpchk GET /
    http-check expect status 200
    server local 127.0.0.1:18221 check inter 1s fall 3 rise 2

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
    if ss -ltn 'sport = :443' | grep -q LISTEN; then break; fi
    sleep 1
done

# keepalived est INSTALLE et NON configure : la mission est de deployer la
# bascule. On s'assure seulement qu'il ne tourne pas avec une configuration
# d'exemple laissee par le paquet.
systemctl disable --now keepalived 2>/dev/null || true
rm -f /etc/keepalived/keepalived.conf
install -d -m 0755 /etc/keepalived

cat > "$WORK/recette.txt" <<RECETTE
# Recette de pub-haproxy-ha.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# LE NOM PUBLIE, et l'adresse par laquelle le service est joint. Cette
# adresse n'appartient a aucune des deux machines au repos : c'est a vous de
# la faire exister, et de la faire se deplacer.

nom_service = service.pub.lab.test
ip_flottante = 10.10.110.200

# LES DEUX POINTS D'ENTREE, par leur nom court et leur adresse propre. Les
# deux doivent pouvoir servir la recette directement, avant toute bascule.

entree = edge 10.10.110.11
entree = edge2 10.10.110.13

# L'AUTORITE qui signe le certificat du service. Les deux points d'entree
# presentent LE MEME certificat : un client qui verifie strictement ne doit
# pas voir un service different selon qui repond.

ca_service = /opt/pub-haproxy-ha/pki/ca.crt

# LES DEUX ROUTES. La publique s'ouvre, la privee est refusee a tout ce qui
# ne vient pas de la machine. La politique doit tenir APRES une bascule.

route_publique = /
route_privee = /prive/

# LE DOSSIER, relu par un humain. Il doit decrire ce que cette bascule ne
# protege pas.

dossier = /opt/pub-haproxy-ha/dossier.md
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"
chown -R student:student "$WORK"

echo "--- point d'entree $MOI pose, sans adresse flottante ---"
ip -o -4 addr show | awk '{print $2, $4}'
curl -sk --max-time 10 https://127.0.0.1/ || true

echo "fixture pub-haproxy-ha posee sur $MOI"
exit 0
