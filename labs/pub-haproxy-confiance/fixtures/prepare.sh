#!/usr/bin/env bash
# Pose la situation : une chaine de confiance entierement debranchee, et rien
# qui le dise.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-confiance.log) 2>&1
set -x

WORK=/opt/pub-haproxy-confiance
PKI="$WORK/pki"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat openssl

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0755 -o student -g student "$PKI"

# ---------------------------------------------------------------------------
# QUATRE AUTORITES. Elles sont distinctes a dessein : la confiance se declare
# par autorite, et une seule autorite pour tout rendrait les contre-tests
# impossibles a construire.
#
#   ca-service    signe le certificat que le proxy presente aux clients ;
#   ca-backend    signe le certificat du backend legitime ;
#   ca-clients    signe les identites clientes acceptees ;
#   ca-etrangere  signe l'IMPOSTEUR et un client non reconnu.
# ---------------------------------------------------------------------------
creer_ca() {
    local nom="$1" sujet="$2"
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout "$PKI/${nom}.key" -out "$PKI/${nom}.crt" \
        -subj "/CN=${sujet}" 2>/dev/null
}

signer() {
    local ca="$1" nom="$2" sujet="$3" san="$4"
    openssl req -newkey rsa:2048 -nodes \
        -keyout "$PKI/${nom}.key" -out "$PKI/${nom}.csr" \
        -subj "$sujet" -addext "subjectAltName=${san}" 2>/dev/null
    # `-copy_extensions copy` : sans elle, le SAN du CSR est silencieusement
    # jete, et le certificat signe ne porte que son CN. Un client strict le
    # refuse alors pour une raison qui ne se lit nulle part dans la commande
    # qui l'a produit.
    openssl x509 -req -in "$PKI/${nom}.csr" \
        -CA "$PKI/${ca}.crt" -CAkey "$PKI/${ca}.key" \
        -out "$PKI/${nom}.crt" -days 365 -copy_extensions copy 2>/dev/null
    rm -f "$PKI/${nom}.csr"
}

creer_ca ca-service "AC de service du lab"
creer_ca ca-backend "AC des backends du lab"
creer_ca ca-clients "AC des clients du lab"
creer_ca ca-etrangere "AC etrangere du lab"

# Le certificat que le proxy presente aux clients.
signer ca-service service "/CN=service.pub.lab.test" \
    "DNS:service.pub.lab.test"
cat "$PKI/service.key" "$PKI/service.crt" > "$PKI/service.pem"

# Le backend legitime, et l'IMPOSTEUR, qui porte LE MEME NOM.
signer ca-backend backend "/CN=backend-interne.lab" "DNS:backend-interne.lab"
signer ca-etrangere imposteur "/CN=backend-interne.lab" \
    "DNS:backend-interne.lab"

# Deux identites clientes : l'une reconnue, l'autre non.
signer ca-clients client-ops "/CN=ops@pub.lab.test/O=Exploitation" \
    "email:ops@pub.lab.test"
cat "$PKI/client-ops.key" "$PKI/client-ops.crt" > "$PKI/client-ops.pem"
signer ca-etrangere client-etranger "/CN=visiteur@ailleurs.test" \
    "email:visiteur@ailleurs.test"
cat "$PKI/client-etranger.key" "$PKI/client-etranger.crt" \
    > "$PKI/client-etranger.pem"

chown -R student:student "$PKI"
chmod 0644 "$PKI"/*.crt "$PKI"/*.pem
chmod 0640 "$PKI"/*.key

# ---------------------------------------------------------------------------
# Les deux backends. Ils parlent HTTPS et RENVOIENT ce qu'ils ont recu : sans
# ce renvoi, « l'identite arrive jusqu'a l'application » ne serait pas
# mesurable, et il faudrait croire le proxy sur parole.
#
# L'imposteur sert LE MEME MARQUEUR que le legitime, et c'est le point : si
# la verification est desactivee, sa reponse est indiscernable d'un succes.
# ---------------------------------------------------------------------------
cat > "$WORK/service.py" <<'PY'
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])
CERT = sys.argv[3]
CLE = sys.argv[4]

INTERESSANTS = (
    "x-forwarded-for",
    "x-forwarded-proto",
    "x-client-dn",
    "x-client-verifie",
)


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        lignes = [
            "pub-haproxy-confiance backend",
            f"origine: {NOM}",
            f"chemin: {self.path}",
            f"pair: {self.client_address[0]}",
        ]
        for entete in INTERESSANTS:
            lignes.append(f"{entete}: {self.headers.get(entete, 'absent')}")
        corps = ("\n".join(lignes) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
contexte.load_cert_chain(CERT, CLE)
serveur = ThreadingHTTPServer(("127.0.0.1", PORT), Service)
serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
serveur.serve_forever()
PY
chmod 0644 "$WORK/service.py"

poser_unite() {
    local nom="$1" origine="$2" port="$3" cert="$4"
    cat > "/etc/systemd/system/pub-haproxy-confiance-${nom}.service" <<UNIT
[Unit]
Description=Backend ${origine} for the HAProxy trust lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/service.py ${origine} ${port} ${PKI}/${cert}.crt ${PKI}/${cert}.key
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}

poser_unite legitime legitime 18161 backend
poser_unite imposteur legitime 18162 imposteur

systemctl daemon-reload
systemctl enable --now pub-haproxy-confiance-legitime.service
systemctl enable --now pub-haproxy-confiance-imposteur.service

for port in 18161 18162; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

# Le nom publie resout sur la machine qui le sert. Les tests, eux,
# interrogent depuis le client avec `curl --resolve` et n'en ont pas besoin ;
# mais tout ce qui tourne SUR la machine, corrige compris, passe par le
# resolveur. Sans cette ligne, une verification locale echoue sur « Name or
# service not known », un message qui parle de DNS la ou le probleme est
# qu'on n'en a pas declare.
grep -q 'dsoxlab-pub-haproxy-confiance' /etc/hosts \
    || echo "127.0.0.1 service.pub.lab.test # dsoxlab-pub-haproxy-confiance" >> /etc/hosts

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-confiance.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-confiance.conf

# ---------------------------------------------------------------------------
# L'etat de depart. Tout repond, et quatre choses sont fausses.
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
    # FAUTE 2 : aucune identite client n'est demandee ni verifiee. La route
    # privee ci-dessous est donc publique.
    bind :443 ssl crt ${PKI}/service.pem

    # FAUTE 3 : `option forwardfor` AJOUTE a l'en-tete recu. Un client qui
    # envoie son propre X-Forwarded-For voit sa valeur arriver EN PREMIER
    # chez l'application, qui lit presque toujours la premiere.
    option forwardfor

    use_backend interne if { path_beg /prive/ }
    use_backend usurpe  if { path_beg /api-usurpe/ }
    default_backend interne

frontend interne_approuve
    # FAUTE 4 : cette ecoute fait confiance a l'en-tete PROXY de qui s'y
    # connecte, et elle est ouverte a tout le reseau. Un client peut donc
    # declarer l'adresse qu'il veut.
    bind :8443 accept-proxy ssl crt ${PKI}/service.pem
    option forwardfor
    default_backend interne

backend interne
    # FAUTE 1 : `verify none`. La liaison est chiffree et l'identite du
    # backend n'est pas regardee : n'importe quel certificat passe.
    server legitime 127.0.0.1:18161 ssl verify none

backend usurpe
    # La meme faute, vers un backend qui presente un certificat signe par une
    # autorite etrangere avec le MEME nom. Sa reponse porte le MEME marqueur
    # que le legitime : si la verification est desactivee, elle est
    # indiscernable d'un succes.
    server imposteur 127.0.0.1:18162 ssl verify none

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

cat > "$WORK/recette.txt" <<RECETTE
# Recette de pub-haproxy-confiance.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# CE QUE LE PROXY PRESENTE AUX CLIENTS :

nom_service = service.pub.lab.test
port_public = 443
ca_service = ${PKI}/ca-service.crt

# L'IDENTITE DU BACKEND. Le backend legitime et l'imposteur portent le MEME
# nom ; seule l'autorite qui les signe les distingue.

nom_backend = backend-interne.lab
ca_backend = ${PKI}/ca-backend.crt
service_legitime = 127.0.0.1:18161
service_imposteur = 127.0.0.1:18162

# LES IDENTITES CLIENTES. Celle que l'autorite des clients signe, et celle
# qu'une autorite etrangere signe.

ca_clients = ${PKI}/ca-clients.crt
client_valide = ${PKI}/client-ops.pem
client_etranger = ${PKI}/client-etranger.pem
cn_attendu = ops@pub.lab.test

# LES TROIS ROUTES. La publique s'ouvre sans identite, la privee l'exige, et
# le canari doit RESTER refuse : c'est lui qui prouve que la verification du
# backend est stricte, donc le retirer revient a retirer la preuve.

route_publique = /
route_privee = /prive/
route_canari = /api-usurpe/

# L'ECOUTE DU SAUT APPROUVE, et l'adresse qu'il a le droit de declarer. Un
# client non approuve ne doit pas pouvoir s'en servir.

port_interne = 8443
adresse_declaree = 203.0.113.9
source_approuvee = 127.0.0.1

socket_admin = /run/haproxy/admin.sock
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "--- etat de depart : tout repond, et quatre choses sont fausses ---"
echo "## la route privee, sans aucune identite :"
curl -sk -o /dev/null -w '%{http_code}\n' --max-time 5 \
    --resolve service.pub.lab.test:443:127.0.0.1 \
    https://service.pub.lab.test/prive/ || true
echo "## le canari, qui devrait etre refuse :"
curl -sk -o /dev/null -w '%{http_code}\n' --max-time 5 \
    --resolve service.pub.lab.test:443:127.0.0.1 \
    https://service.pub.lab.test/api-usurpe/ || true
echo "## l'adresse qu'un client se declare :"
curl -sk --max-time 5 -H 'X-Forwarded-For: 1.2.3.4' \
    --resolve service.pub.lab.test:443:127.0.0.1 \
    https://service.pub.lab.test/ 2>/dev/null \
    | grep -i x-forwarded-for || true

echo "fixture pub-haproxy-confiance posee"
exit 0
