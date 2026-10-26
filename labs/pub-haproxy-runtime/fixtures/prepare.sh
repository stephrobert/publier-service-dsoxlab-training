#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-runtime.log) 2>&1
set -x

WORK=/opt/pub-haproxy-runtime

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete

# ---------------------------------------------------------------------------
# Trois identites de test, sans mot de passe et sans sudo. Elles existent
# pour que « qui peut faire quoi » soit mesurable autrement qu'en relisant
# une ligne de configuration.
# ---------------------------------------------------------------------------
for groupe in exploitants observateurs; do
    getent group "$groupe" >/dev/null || groupadd --system "$groupe"
done

creer_identite() {
    local nom="$1" groupe="${2:-}"
    if ! id -u "$nom" >/dev/null 2>&1; then
        useradd --system --create-home --shell /bin/bash "$nom"
    fi
    if [ -n "$groupe" ]; then
        usermod -aG "$groupe" "$nom"
    fi
}

creer_identite exploitant exploitants
creer_identite veilleur observateurs
# Celle-ci n'appartient a aucun groupe : c'est le contre-test.
creer_identite intrus

cat > "$WORK/service.py" <<'PY'
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOM = sys.argv[1]
PORT = int(sys.argv[2])


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        corps = (
            f"pub-haproxy-runtime service {NOM}\n"
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

poser_unite() {
    local nom="$1" port="$2"
    cat > "/etc/systemd/system/pub-haproxy-runtime-${nom}.service" <<UNIT
[Unit]
Description=Backend ${nom} for the HAProxy runtime lab
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

poser_unite a 18191
poser_unite b 18192
systemctl daemon-reload
systemctl enable --now pub-haproxy-runtime-a.service
systemctl enable --now pub-haproxy-runtime-b.service
for port in 18191 18192; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-runtime.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-runtime.conf
install -d -m 0755 -o haproxy -g haproxy /var/lib/haproxy

cat > /etc/haproxy/haproxy.cfg <<'CFG'
global
    log /dev/log local0
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon
    maxconn 2048

    # FAUTE 1 : mode 666. N'importe quel compte de la machine peut piloter
    # ce proxy. Rien ne le signale, et tout fonctionne.
    # FAUTE 2 : un seul socket, en `level admin`. Ce qui a besoin de LIRE
    # recoit le droit d'AGIR.
    stats socket /run/haproxy/admin.sock mode 666 level admin
    stats timeout 30s

    # FAUTE 3 : aucun `server-state-file`, aucun
    # `load-server-state-from-file`. Un rechargement oublie toute decision
    # prise a chaud.

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
    balance roundrobin
    server a 127.0.0.1:18191 check
    server b 127.0.0.1:18192 check

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
# Recette de pub-haproxy-runtime.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# DEUX VOIES D'ACCES, ET DEUX DROITS DIFFERENTS
#
# Lire l'etat et agir dessus ne demandent pas le meme droit, et ne passent
# donc pas par le meme socket. Chacun appartient a un groupe, et aucun n'est
# ouvert au monde.

socket_lecture = /run/haproxy/lecture.sock
groupe_lecture = observateurs
identite_lecture = veilleur

socket_admin = /run/haproxy/admin.sock
groupe_admin = exploitants
identite_admin = exploitant

# Une identite qui n'appartient a aucun des deux groupes. Elle ne doit
# pouvoir NI lire NI agir : c'est le contre-test de la separation.

identite_interdite = intrus

# CE QUI DOIT SURVIVRE A UN RECHARGEMENT
#
# Une decision prise a chaud ne doit pas etre oubliee par un `reload`
# declenche par autre chose. Un fichier marqueur ne repond pas a la
# demande : la validation retire un serveur, recharge, et regarde l'etat
# que HAProxy RAPPORTE.

backend = applicatif
serveur_a = a
serveur_b = b

# LE RETOUR A L'ETAT NOMINAL. Il se livre comme un executable, parce que la
# validation l'EXECUTE : une methode de retour qui n'a jamais ete jouee
# n'est pas une methode de retour.

retour_nominal = /opt/pub-haproxy-runtime/revenir-au-nominal

# LE DOSSIER, relu par un humain : quelle decision, par quelle voie, et
# comment on revient.

dossier = /opt/pub-haproxy-runtime/dossier.md
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "--- etat de depart : n'importe qui peut piloter le proxy ---"
ls -l /run/haproxy/admin.sock
sudo -u intrus sh -c "echo 'show info' | socat -t2 stdio /run/haproxy/admin.sock | head -3" || true

echo "fixture pub-haproxy-runtime posee"
exit 0
