#!/usr/bin/env bash
# Pose la situation : HAProxy sert l'application en HTTP, et rien en HTTPS.
#
# CE QUE LE SETUP NE FAIT PAS : il n'obtient aucun certificat, ne declare
# aucun `bind ssl`, n'ecrit aucune liste de certificats, ne route pas le defi
# ACME, et n'ecrit aucun script de renouvellement. Les quatre controles
# portent sur ces gestes.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-tls-stable.log) 2>&1
set -x

WORK=/opt/pub-haproxy-tls-stable
PARTAGE=/opt/pub-traefik-acme

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat openssl

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete

# La racine de l'autorite de test, celle qui signe les certificats remis
# pendant cette session. Elle vient de la plateforme partagee : la recopier
# ici evite a l'apprenant de la chercher, sans en faire une seconde verite.
install -m 0644 -o student -g docker \
    "$PARTAGE/pebble-root.pem" "$WORK/pebble-root.pem"

# Le repertoire de travail du client ACME. Il porte le compte, donc une cle
# privee : il n'est lisible que par root et par student, et par personne
# d'autre.
install -d -m 0750 -o student -g docker "$WORK/acme"
install -m 0644 -o student -g docker \
    "$PARTAGE/pebble-root.pem" "$WORK/acme/pebble-root.pem"

# ---------------------------------------------------------------------------
# Le client ACME fourni. L'image est epinglee par le catalogue ; l'enveloppe
# existe pour que l'apprenant ecrive `lego ... run` et non quinze arguments
# de docker, qui ne lui apprendraient rien sur ACME.
#
# `--network acme-renewal` : c'est par la que le client joint l'autorite.
# `-p 127.0.0.1:5002:5002` : c'est par la que HAProxy joindra le serveur de
# defi du client. Les deux sont deja branches : ce qui manque est la ROUTE
# dans HAProxy.
# ---------------------------------------------------------------------------
cat > "$WORK/lego" <<WRAPPER
#!/usr/bin/env bash
# Client ACME externe, dans l'image epinglee du catalogue.
#
# Exemple d'appel :
#   sudo $WORK/lego --server https://pub-renewal-pebble:14000/dir \\
#       --email ops@pub.lab.test --accept-tos \\
#       --http --http.port :5002 -d alpha.pub.lab.test run
set -euo pipefail
exec docker run --rm \\
    --network acme-renewal \\
    -p 127.0.0.1:5002:5002 \\
    -v $WORK/acme:/data \\
    -e LEGO_CA_CERTIFICATES=/data/pebble-root.pem \\
    ${IMG_LEGO} --path /data "\$@"
WRAPPER
chmod 0755 "$WORK/lego"
chown root:root "$WORK/lego"

# ---------------------------------------------------------------------------
# L'application a publier.
# ---------------------------------------------------------------------------
cat > "$WORK/service.py" <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 18151


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        hote = self.headers.get("Host", "absent")
        corps = (
            f"pub-haproxy-tls-stable service\n"
            f"chemin: {self.path}\n"
            f"host-recu: {hote}\n"
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

cat > /etc/systemd/system/pub-haproxy-tls-stable-service.service <<UNIT
[Unit]
Description=Application for the HAProxy certificate cycle lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/service.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

# ---------------------------------------------------------------------------
# De quoi que la plateforme ACME revienne au demarrage. Le dernier controle
# redemarre la machine PUIS renouvelle : sans cette unite, l'autorite serait
# absente et le controle mesurerait l'absence de docker, pas le travail de
# l'apprenant.
# ---------------------------------------------------------------------------
cat > /etc/systemd/system/pub-haproxy-tls-stable-acme.service <<UNIT
[Unit]
Description=Bring the ACME test platform back after a reboot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose -f ${PARTAGE}/platform.yaml up -d
ExecStop=/bin/true

[Install]
WantedBy=multi-user.target
UNIT

# Le repertoire du socket d'administration survit au vidage de /run. Ce lab
# ne porte pas sur l'installation : la condition est donc fournie.
cat > /etc/tmpfiles.d/pub-haproxy-tls-stable.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-tls-stable.conf

systemctl daemon-reload
systemctl enable --now pub-haproxy-tls-stable-service.service
systemctl enable pub-haproxy-tls-stable-acme.service

for _ in $(seq 60); do
    if ss -ltn 'sport = :18151' | grep -q LISTEN; then break; fi
    sleep 1
done

# Le repertoire des certificats. root:root et 0750 : HAProxy lit ses
# certificats en tant que root, avant d'abandonner ses privileges.
install -d -m 0750 -o root -g root /etc/haproxy/certs

cat > /etc/haproxy/haproxy.cfg <<'CFG'
# Etat de depart du lab pub-haproxy-tls-stable.
#
# L'application est publiee en HTTP, et c'est tout. Il n'y a ni certificat,
# ni `bind ssl`, ni route pour le defi ACME.
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
    default_backend applicatif

backend applicatif
    server app 127.0.0.1:18151 check
CFG
chmod 0644 /etc/haproxy/haproxy.cfg

haproxy -c -f /etc/haproxy/haproxy.cfg
systemctl enable haproxy
systemctl restart haproxy

for _ in $(seq 60); do
    if ss -ltn 'sport = :80' | grep -q LISTEN; then break; fi
    sleep 1
done

cat > "$WORK/recette.txt" <<RECETTE
# Recette de pub-haproxy-tls-stable.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# LES DEUX NOMS A SERVIR EN HTTPS, chacun avec SON certificat. Un seul
# certificat portant les deux noms en SAN ne repond pas a la recette : le lab
# porte sur la selection par SNI, et deux certificats sont le seul moyen de
# la mesurer.

nom_a = alpha.pub.lab.test
nom_b = beta.pub.lab.test

# OU HAPROXY LIT SES CERTIFICATS. Un fichier par nom, cle et chaine
# concatenees, lisible par root seul.

pem_a = /etc/haproxy/certs/alpha.pub.lab.test.pem
pem_b = /etc/haproxy/certs/beta.pub.lab.test.pem

# L'AUTORITE DE TEST, son annuaire, et la racine qui l'authentifie.

annuaire = https://pub-renewal-pebble:14000/dir
racine_acme = ${WORK}/pebble-root.pem

# LE CLIENT ACME FOURNI, et le port sur lequel son serveur de defi ecoute.
# Ce port est publie sur la boucle locale ; ce qui manque est la route qui
# mene le defi jusqu'a lui.

client_acme = ${WORK}/lego
port_defi = 5002
chemin_defi = /.well-known/acme-challenge/

# LE SCRIPT DE RENOUVELLEMENT A LIVRER. La validation l'EXECUTE : un cycle
# ne se constate pas apres coup, il se joue.

renouveler = ${WORK}/renouveler

# Par ou charger un certificat SANS redemarrer, et en le faisant verifier
# avant qu'il entre en service :

socket_admin = /run/haproxy/admin.sock
RECETTE
chown student:docker "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "fixture pub-haproxy-tls-stable posee"
exit 0
