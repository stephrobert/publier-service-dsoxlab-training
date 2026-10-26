#!/usr/bin/env bash
# Pose la situation : un proxy dont toutes les bornes de temps valent la
# meme chose, qui reessaie tout, et qui ne colle aucun client a rien.
#
# LES QUATRE FAUTES
#
#   1. une seule valeur pour toutes les phases, et PAS de `timeout queue` :
#      une connexion impossible, une file pleine et une reponse lente
#      prennent le meme temps et rendent le meme signal. Un exploitant ne
#      peut pas dire laquelle des trois il regarde ;
#   2. dix secondes d'inactivite, et aucun `timeout tunnel` : le flux
#      d'evenements meurt entre deux battements, et le WebSocket meurt dans
#      un silence normal ;
#   3. `retry-on all-retryable-errors` : une ecriture dont la REPONSE s'est
#      perdue est rejouee, et le travail a lieu deux fois ;
#   4. aucune politique de session : une requete sur deux change d'instance,
#      et l'etat que le client croit avoir n'y est pas.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-haproxy-flux-delais.log) 2>&1
set -x

WORK=/opt/pub-haproxy-flux-delais

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -o student -g student -m 0644 /tmp/pub-flux-delais-backends.py \
    "$WORK/backends.py"

cat > /etc/systemd/system/pub-haproxy-flux-delais-backends.service <<UNIT
[Unit]
Description=Backends for the HAProxy timing and long-stream lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${WORK}/backends.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now pub-haproxy-flux-delais-backends.service
for port in 18181 18182 18183; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

BATTEMENT="$(python3 "$WORK/backends.py" --battement)"

install -d -m 0755 -o haproxy -g haproxy /run/haproxy
cat > /etc/tmpfiles.d/pub-haproxy-flux-delais.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-haproxy-flux-delais.conf

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

    # FAUTE 1 : une seule valeur pour tout, et pas de `timeout queue`. Les
    # trois phases deviennent indiscernables.
    # FAUTE 2 : dix secondes d'inactivite, et aucun `timeout tunnel`.
    timeout connect 10s
    timeout client  10s
    timeout server  10s

    # FAUTE 3 : HAProxy rejoue tout ce qui peut l'etre, y compris une
    # requete dont la reponse s'est perdue APRES que le serveur l'a
    # traitee.
    retries 3
    retry-on all-retryable-errors

frontend public
    bind :80

    acl est_ws path_beg /ws
    acl est_injection_connexion path_beg /injection/connexion
    acl est_injection_file      path_beg /injection/file
    acl est_bascule             path_beg /injection/bascule

    use_backend temps_reel         if est_ws
    use_backend injection_connexion if est_injection_connexion
    use_backend injection_file      if est_injection_file
    use_backend bascule             if est_bascule

    default_backend applicatif

backend applicatif
    # FAUTE 4 : aucune politique de session. Une requete sur deux change
    # d'instance, et l'etat que le client croit avoir n'y est pas.
    balance roundrobin
    server a 127.0.0.1:18181 check
    server b 127.0.0.1:18182 check

backend temps_reel
    server ws 127.0.0.1:18183

# Une adresse de la plage de documentation TEST-NET-1 : elle n'est routee
# nulle part, donc toute tentative de connexion reste sans reponse. C'est le
# seul moyen simple d'injecter une phase de CONNEXION lente, qu'aucune
# application ne peut simuler depuis l'interieur.
backend injection_connexion
    server inatteignable 192.0.2.1:80

# Une seule connexion a la fois vers le serveur : la deuxieme requete attend
# dans la file du backend, et c'est la phase que `timeout queue` borne.
backend injection_file
    http-request set-path /lent
    server a 127.0.0.1:18181 maxconn 1

# Un serveur mort et un serveur sain : c'est ici que se mesure la CAPACITE
# qu'il ne faut pas perdre en restreignant les reessais. Une lecture dont la
# connexion echoue doit encore aboutir.
backend bascule
    option redispatch
    server mort 192.0.2.1:80
    server a 127.0.0.1:18181

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

cat > "$WORK/recette.txt" <<RECETTE
# Recette de pub-haproxy-flux-delais.
#
# Chaque ligne « cle = valeur » est lue par la validation. Elle dit ce qui
# doit arriver, jamais avec quelles directives l'obtenir.
#
# LES TROIS PHASES, ET LEURS BORNES. Elles sont DIFFERENTES a dessein : une
# borne par phase est la seule facon qu'un exploitant ait de savoir laquelle
# des trois il regarde, a partir du seul temps ecoule.

timeout_connexion = 2
tentatives = 2
timeout_file = 10
timeout_serveur = 20

# Une connexion impossible doit donc rendre la main en « timeout_connexion x
# tentatives » secondes, une file pleine en « timeout_file », et une reponse
# lente en « timeout_serveur ». Trois durees distinctes, trois diagnostics.

# LES FLUX LONGS. Le battement de l'application est LENT : c'est le silence
# entre deux evenements qui met une borne d'inactivite a l'epreuve.

duree_flux = 30
battement = ${BATTEMENT}
timeout_tunnel = 60

# LES ROUTES.

route_injection_connexion = /injection/connexion
route_injection_file = /injection/file
route_bascule = /injection/bascule
route_lent = /lent
route_sse = /sse
route_ws = /ws
route_ecrire = /ecrire
route_session_ouvrir = /session/ouvrir
route_session_lire = /session/lire

# LES COMPTEURS METIER, lus sur la boucle locale. C'est par eux que se
# mesure une ecriture dupliquee : le client, lui, n'a rien recu.

compteur_a = http://127.0.0.1:18181/ecritures
compteur_b = http://127.0.0.1:18182/ecritures
backend_applicatif = applicatif

# LES NOMS DES DEUX SERVEURS dans le backend. Le socket d'administration
# adresse un serveur par son NOM : la validation retire du service celui qui
# detient une session, donc ces noms font partie du contrat et ne se
# renomment pas. Ils correspondent au nom que chaque instance annonce.

serveur_a = a
serveur_b = b

# LE DOSSIER a rendre, relu par un humain. Il doit dire les limites de la
# politique de session retenue.

dossier = /opt/pub-haproxy-flux-delais/dossier.md
socket_admin = /run/haproxy/admin.sock
RECETTE
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

echo "--- etat de depart : les trois phases rendent le meme temps ---"
for route in /injection/connexion /lent?duree=60; do
    echo "## $route"
    curl -s -o /dev/null -w '%{http_code} en %{time_total}s\n' \
        --max-time 40 "http://127.0.0.1${route}" || true
done

echo "fixture pub-haproxy-flux-delais posee"
exit 0
