#!/usr/bin/env bash
# Pose le banc de l'epreuve pub-epreuve-haproxy sur edge.lab.
#
# DEUX PARTIES INDEPENDANTES
#
#   1. LA LIVRAISON. HAProxy est installe et n'a AUCUNE mission : ni listener,
#      ni certificat, ni route. Deux services (catalogue, notifications) ont
#      ete demarres a la hate et ecoutent sur TOUTES les interfaces. Une
#      autorite de test et un client ACME sont fournis. L'apprenant construit
#      la livraison.
#
#   2. LA PANNE. Une seconde instance HAProxy, `archives`, tourne depuis le
#      debut avec son propre fichier, son propre port et ses propres
#      backends. Une panne, tiree au sort parmi cinq familles, a ete posee
#      dessus. La famille reelle est gardee hors de portee dans /root.
#
# CE QUE LE SETUP NE FAIT PAS : il n'ecrit aucun `frontend` pour la livraison,
# n'obtient aucun certificat, n'ecrit ni `renouveler` ni `restaurer`, ne
# ferme pas les backends au reseau, et ne depose aucune sauvegarde de la
# configuration. Les controles portent sur ces gestes.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-epreuve-haproxy.log) 2>&1
set -x

WORK=/opt/pub-epreuve-haproxy
PARTAGE=/opt/pub-traefik-acme
DONNEES=/var/lib/pub-epreuve-haproxy
SAUVEGARDE=/var/backups/pub-epreuve-haproxy
ARCH_WORK=/opt/pub-epreuve-haproxy-archives
ARCH_PKI="$ARCH_WORK/pki"
ARCH_ETC=/etc/pub-epreuve-haproxy-archives
SECRET=/root/.pub-epreuve-haproxy-secret.yaml

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl socat openssl

# ---------------------------------------------------------------------------
# Repartir de zero : un rejeu ne doit rien trouver du passage precedent.
# ---------------------------------------------------------------------------
for unite in \
    pub-epreuve-haproxy-catalogue pub-epreuve-haproxy-notifications \
    pub-epreuve-haproxy-archives pub-epreuve-haproxy-archives-backends; do
    systemctl stop "$unite.service" 2>/dev/null || true
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
rm -rf "$DONNEES" "$SAUVEGARDE" "$ARCH_WORK" "$ARCH_ETC"
install -d -m 0755 "$DONNEES" "$SAUVEGARDE"

# ---------------------------------------------------------------------------
# L'autorite de test : ses DEUX racines ne servent pas a la meme chose.
#
#   pebble.minica.pem  authentifie l'API de l'autorite. C'est celle qu'un
#                      client approuve pour LUI PARLER ;
#   pebble-root.pem    est la racine des certificats qu'elle EMET. C'est celle
#                      qu'on approuve pour verifier le certificat du service.
#
# La plateforme (Pebble et son repondeur de defis) a ete posee par le
# playbook avant ce script. Pebble tire une NOUVELLE racine et oublie ses
# comptes a chaque demarrage : cette racine-ci vaut pour la session en cours.
# ---------------------------------------------------------------------------
install -m 0644 -o student -g docker "$PARTAGE/pebble-root.pem" "$WORK/pebble-root.pem"
install -d -m 0750 -o student -g docker "$WORK/acme"
install -m 0644 -o student -g docker "$PARTAGE/pebble-root.pem" "$WORK/acme/pebble-root.pem"
install -m 0644 -o student -g docker "$PARTAGE/pebble.minica.pem" "$WORK/acme/pebble.minica.pem"
install -m 0644 -o student -g docker "$PARTAGE/pebble.minica.pem" "$WORK/pebble.minica.pem"

# Le client ACME fourni. L'enveloppe existe pour que l'apprenant ecrive
# `lego run ...` et non quinze arguments de docker. La COMMANDE d'abord, ses
# options ensuite : en lego 5, `--server`, `--email` et `--http` sont des
# options de `run`. `LEGO_PATH` et non `--path`, qui n'est plus global.
cat > "$WORK/lego" <<WRAPPER
#!/usr/bin/env bash
# Client ACME externe, dans l'image epinglee du catalogue.
#
# Exemple d'appel :
#   sudo $WORK/lego run --server https://pebble:14000/dir \\
#       --email ops@epreuve.test --accept-tos \\
#       --http --http.address :5002 -d nom.epreuve.test
#
# \`pebble\` et non \`pub-renewal-pebble\` : le certificat de l'API porte
# \`localhost\` et \`pebble\` en noms alternatifs, pas le nom du conteneur.
set -euo pipefail
exec docker run --rm \\
    --network acme-renewal \\
    -p 127.0.0.1:5002:5002 \\
    -v $WORK/acme:/data \\
    -e LEGO_CA_CERTIFICATES=/data/pebble.minica.pem \\
    -e LEGO_PATH=/data \\
    ${IMG_LEGO} "\$@"
WRAPPER
chmod 0755 "$WORK/lego"
chown root:root "$WORK/lego"

# ---------------------------------------------------------------------------
# De quoi que la plateforme ACME revienne apres un redemarrage de la machine.
# Sans cette unite, l'autorite serait absente au retour et la validation
# mesurerait l'absence de docker, pas le travail de l'apprenant.
# ---------------------------------------------------------------------------
cat > /etc/systemd/system/pub-epreuve-haproxy-acme.service <<UNIT
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

# ---------------------------------------------------------------------------
# LES DEUX SERVICES DE LA LIVRAISON.
#
# Ils ecoutent sur TOUTES les interfaces (`BIND=0.0.0.0`), comme s'ils avaient
# ete lances a la hate. Les fermer au reseau est un geste de l'apprenant. Le
# service `catalogue` lit sa donnee metier dans un fichier a chaque requete.
# ---------------------------------------------------------------------------
install -m 0644 /tmp/pub-epreuve-haproxy-services.py "$WORK/services.py"

VALEUR=$(( (RANDOM % 900) + 100 ))
PRODUITS=$(( (RANDOM % 90) + 10 ))
cat > "$DONNEES/catalogue.json" <<JSON
{"valeur": $VALEUR, "produits": $PRODUITS}
JSON
chmod 0644 "$DONNEES/catalogue.json"
# La sauvegarde de reference : prise ici, avant tout travail. Personne n'a
# encore prouve qu'elle restaure quoi que ce soit.
cp "$DONNEES/catalogue.json" "$SAUVEGARDE/catalogue.json.bak"
chmod 0644 "$SAUVEGARDE/catalogue.json.bak"

poser_service() {
    local nom="$1" port="$2"
    cat > "/etc/systemd/system/pub-epreuve-haproxy-${nom}.service" <<UNIT
[Unit]
Description=Service ${nom} (epreuve pub-epreuve-haproxy)
After=network.target

[Service]
Type=simple
Environment=BIND=0.0.0.0
Environment=PORT=${port}
Environment=DONNEES=${DONNEES}/catalogue.json
ExecStart=/usr/bin/python3 ${WORK}/services.py ${nom}
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}
poser_service catalogue 18301
poser_service notifications 18302

# Le repertoire du socket d'administration survit au vidage de /run. Cette
# epreuve ne porte pas sur l'installation : la condition est fournie.
cat > /etc/tmpfiles.d/pub-epreuve-haproxy.conf <<'TMPFILES'
d /run/haproxy 0755 haproxy haproxy -
TMPFILES
systemd-tmpfiles --create /etc/tmpfiles.d/pub-epreuve-haproxy.conf

# HAProxy est installe, enregistre au demarrage par le paquet, et SANS mission.
systemctl stop haproxy || true
systemctl disable haproxy || true
rm -f /run/haproxy/admin.sock
install -d -m 0755 /etc/haproxy /etc/haproxy/conf.d
install -d -m 0750 -o root -g root /etc/haproxy/certs
cat > /etc/haproxy/haproxy.cfg <<'CFG'
# Point de depart de l'epreuve pub-epreuve-haproxy : aucun listener.
global
    log /dev/log local0
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon

defaults
    log     global
    option  dontlognull
    timeout connect 5s
    timeout client  30s
    timeout server  30s
CFG
chmod 0644 /etc/haproxy/haproxy.cfg

# ---------------------------------------------------------------------------
# LA PANNE : l'instance `archives`.
# ---------------------------------------------------------------------------
install -d -m 0755 "$ARCH_WORK" "$ARCH_PKI" "$ARCH_ETC"
install -m 0644 /tmp/pub-epreuve-haproxy-incident.py "$ARCH_WORK/incident.py"

creer_ca() {
    # `keyUsage` EXPLICITE : une autorite sans cette extension passe
    # `openssl verify` mais echoue en verification STRICTE, celle qu'exige un
    # `verify required`.
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout "$ARCH_PKI/$1.key" -out "$ARCH_PKI/$1.crt" -subj "/CN=$2" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
}
signer() {
    local ca="$1" nom="$2" cn="$3"
    openssl req -newkey rsa:2048 -nodes -keyout "$ARCH_PKI/$nom.key" \
        -out "$ARCH_PKI/$nom.csr" -subj "/CN=$cn" \
        -addext "subjectAltName=DNS:$cn" 2>/dev/null
    openssl x509 -req -in "$ARCH_PKI/$nom.csr" -CA "$ARCH_PKI/$ca.crt" \
        -CAkey "$ARCH_PKI/$ca.key" -CAcreateserial \
        -out "$ARCH_PKI/$nom.crt" -days 365 -copy_extensions copy 2>/dev/null
    rm -f "$ARCH_PKI/$nom.csr"
}
creer_ca ca-archives "AC des archives du banc"
creer_ca ca-etrangere "AC etrangere du banc"
signer ca-archives api "api.archives.lab"
signer ca-etrangere imposteur "api.archives.lab"
chmod 0644 "$ARCH_PKI"/*.crt
chmod 0640 "$ARCH_PKI"/*.key
chgrp -R student "$ARCH_PKI"

grep -q 'dsoxlab-pub-epreuve-haproxy' /etc/hosts \
    || echo "127.0.0.1 api.archives.lab # dsoxlab-pub-epreuve-haproxy" >> /etc/hosts

cat > /etc/systemd/system/pub-epreuve-haproxy-archives-backends.service <<UNIT
[Unit]
Description=Backends of the archives instance (epreuve pub-epreuve-haproxy)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${ARCH_WORK}/incident.py ${ARCH_PKI}
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

# L'unite reprend celle du paquet Debian : `-Ws` (maitre-ouvriers, notification
# systemd), validation avant demarrage, rechargement par USR2.
#
# MESURE DU 2026-10-31 : apres le redemarrage du dernier test, la validation
# `haproxy -c` echouait cinq fois dans la meme seconde, puis systemd renoncait
# (« Start request repeated too quickly »), alors que la meme configuration se
# chargeait avant le redemarrage. L'echec est transitoire, en tout debut de
# demarrage. L'unite reessaie donc toutes les deux secondes sans plafond :
# l'instance archives est au banc, elle doit revenir seule.
cat > /etc/systemd/system/pub-epreuve-haproxy-archives.service <<UNIT
[Unit]
Description=HAProxy instance for the archives service (epreuve pub-epreuve-haproxy)
After=network-online.target pub-epreuve-haproxy-archives-backends.service
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Environment=CONFIG=${ARCH_ETC}/haproxy.cfg
Environment=PIDFILE=/run/pub-epreuve-haproxy-archives.pid
ExecStartPre=/usr/sbin/haproxy -f \$CONFIG -c -q
ExecStart=/usr/sbin/haproxy -Ws -f \$CONFIG -p \$PIDFILE
ExecReload=/usr/sbin/haproxy -f \$CONFIG -c -q
ExecReload=/bin/kill -USR2 \$MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=2
SuccessExitStatus=143
Type=notify

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now pub-epreuve-haproxy-archives-backends.service
for port in 18311 18312 18313 18314; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

# L'ETAT SAIN, ecrit une fois ; la variante l'abime ensuite.
ecrire_cfg_saine() {
cat > "$ARCH_ETC/haproxy.cfg" <<CFG
global
    # Les journaux vont sur la sortie standard : ils se lisent avec
    # \`journalctl -u pub-epreuve-haproxy-archives\`.
    log stdout format raw local0
    user haproxy
    group haproxy
    maxconn 1024
    stats socket /run/pub-epreuve-haproxy-archives.sock mode 660 level admin
    stats timeout 30s

defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    timeout connect 3s
    timeout queue   5s
    timeout client  20s
    timeout server  8s

backend compteurs
    stick-table type ip size 100 expire 60s store http_req_rate(10s)

frontend archives
    bind :8088

    http-request track-sc0 src table compteurs
    http-request deny deny_status 429 if { sc_http_req_rate(0) gt 60 }

    acl est_v2     path_beg /v2/
    acl est_usurpe path_beg /usurpe/

    use_backend usurpe if est_usurpe
    use_backend api    if est_v2
    default_backend web

backend web
    balance roundrobin
    option httpchk GET /ready
    http-check expect status 200
    server web 127.0.0.1:18311 check inter 1s fall 3 rise 2
    server degrade 127.0.0.1:18312 check inter 1s fall 3 rise 2

backend api
    option httpchk GET /ready
    http-check expect status 200
    server api api.archives.lab:18313 check inter 1s fall 3 rise 2 ssl verify required ca-file ${ARCH_PKI}/ca-archives.crt sni str(api.archives.lab) verifyhost api.archives.lab

backend usurpe
    server imposteur 127.0.0.1:18314 ssl verify required ca-file ${ARCH_PKI}/ca-archives.crt sni str(api.archives.lab) verifyhost api.archives.lab
CFG
chmod 0644 "$ARCH_ETC/haproxy.cfg"
}

ecrire_cfg_saine
haproxy -c -f "$ARCH_ETC/haproxy.cfg"
systemctl enable --now pub-epreuve-haproxy-archives.service
for _ in $(seq 60); do
    if ss -ltn 'sport = :8088' | grep -q LISTEN; then break; fi
    sleep 1
done

# LA VARIANTE : tiree au hasard, notee pour la seule validation.
FAMILLE="$(printf 'routage\nsonde\nconfiance\nlimite\ndelai\n' | shuf -n 1)"
case "$FAMILLE" in
routage)
    # Une ACL de chemin exact remplace le prefixe : /v2/produits n'est plus
    # reconnu, et le trafic part sur l'application par defaut (un 200 avec le
    # mauvais marqueur).
    sed -i 's|acl est_v2     path_beg /v2/|acl est_v2     path /v2/|' "$ARCH_ETC/haproxy.cfg"
    ;;
sonde)
    # La sonde interroge un chemin qui n'existe pas : tous les serveurs
    # tombent, les sains compris.
    sed -i 's|option httpchk GET /ready|option httpchk GET /sante|g' "$ARCH_ETC/haproxy.cfg"
    ;;
confiance)
    # Le nom verifie ne correspond plus au certificat du backend legitime.
    sed -i '/^backend api$/,/^backend usurpe$/ s|verifyhost api.archives.lab|verifyhost api.archive.lab|' \
        "$ARCH_ETC/haproxy.cfg"
    ;;
limite)
    # Un seuil que le trafic normal depasse : tout finit en 429.
    sed -i 's|sc_http_req_rate(0) gt 60|sc_http_req_rate(0) gt 2|' "$ARCH_ETC/haproxy.cfg"
    ;;
delai)
    # La borne de reponse devient plus courte que la route lente saine.
    sed -i 's|timeout server  8s|timeout server  1s|' "$ARCH_ETC/haproxy.cfg"
    ;;
esac

cat > "$ARCH_ETC/notes-exploitation.txt" <<'NOTES'
# Notes d'exploitation de l'instance archives, laissees par l'equipe precedente.
#
# - /usurpe/ mene a un backend dont le certificat est signe par une autorite
#   etrangere. Il DOIT rester refuse : c'est ce qui prouve que la verification
#   TLS est stricte.
# - le serveur `degrade` est vivant et en echec, laisse declare expres. Il
#   DOIT rester hors service.
# - la limite de debit et la borne d'attente sur le serveur font partie de
#   l'etat sain.
NOTES
chmod 0644 "$ARCH_ETC/notes-exploitation.txt"

systemctl restart pub-epreuve-haproxy-archives.service || true
sleep 3

install -d -m 0700 /root
cat > "$SECRET" <<YAML
incident: ${FAMILLE}
YAML
chmod 0600 "$SECRET"

# ---------------------------------------------------------------------------
# La recette et la consigne.
# ---------------------------------------------------------------------------
cat > "$WORK/recette.txt" <<RECETTE
# Recette de pub-epreuve-haproxy.
#
# Elle dit ce qui doit arriver, jamais avec quelles directives l'obtenir.
# Toute la configuration de la livraison tient dans /etc/haproxy/haproxy.cfg.
#
# ---- PARTIE 1 : LA LIVRAISON (edge.lab, point d'entree HAProxy) ----------
#
# Les deux noms publies, en HTTPS sur le port 443, et leur service :

nom_catalogue = catalogue.epreuve.test
nom_notifications = notifications.epreuve.test
service_catalogue = 127.0.0.1:18301
service_notifications = 127.0.0.1:18302
unites_services = pub-epreuve-haproxy-catalogue.service pub-epreuve-haproxy-notifications.service

# Un nom inconnu n'atteint aucun des deux services. Le port 80 redirige vers
# HTTPS, sauf le defi ACME.
#
# Les certificats : un par nom, obtenus aupres de l'autorite de test, valables
# CINQ MINUTES. Le cycle complet est un script que vous livrez, et que la
# validation EXECUTE (plusieurs fois, y compris apres un redemarrage) :

annuaire = https://pebble:14000/dir
racine_acme = $WORK/pebble-root.pem
client_acme = $WORK/lego
port_defi = 5002
renouveler = $WORK/renouveler
socket_admin = /run/haproxy/admin.sock

# La politique d'acces :
#  - /admin et tout ce qui commence par /admin exigent une identite HTTP
#    Basic : ops / Epreuve-Admin-Only. Sans elle, un refus (401 ou 403).
#  - l'adresse source vue par les services est celle du client. Un client ne
#    choisit pas la sienne par un en-tete ; le protocole d'origine (https) est
#    transmis.
#  - au-dela de 30 requetes en 10 secondes depuis une meme adresse source vers
#    le catalogue : refus en 429. Un client modere n'est jamais refuse, et la
#    limite se relache d'elle-meme.
#  - les services et l'administration de HAProxy ne sont joignables que
#    depuis edge.lab. Seuls les ports 22, 80, 443 et 8088 (partie 2) ecoutent
#    sur le reseau.

# L'exploitation :
#  - le flux de notifications (/flux, evenements espaces de 35 secondes, 75
#    secondes au total) arrive entier, sans coupure.
#  - les metriques Prometheus de HAProxy sont servies en HTTP sur
#    127.0.0.1:9101, chemin /metrics, et nulle part ailleurs. Elles montrent le
#    trafic et l'etat de chaque serveur.

metriques = 127.0.0.1:9101/metrics
flux = /flux

# La reprise :
#  - la donnee metier du catalogue vit dans $DONNEES/catalogue.json. Sa
#    sauvegarde est $SAUVEGARDE/catalogue.json.bak.
#  - vous deposez la sauvegarde de votre configuration dans
#    $SAUVEGARDE/haproxy.cfg.bak.
#  - le script $WORK/restaurer, executable, remet la donnee ET la
#    configuration depuis ces sauvegardes, puis remet HAProxy en service. Il ne
#    touche ni aux certificats ni aux sauvegardes.
#  - apres un redemarrage de la machine, tout revient seul.

donnees = $DONNEES/catalogue.json
sauvegarde = $SAUVEGARDE
restaurer = $WORK/restaurer

# ---- PARTIE 2 : LA PANNE (instance HAProxy « archives », independante) ----
#
# Une seconde instance HAProxy sert l'application « archives » sur le port
# 8088. Elle a son fichier, son unite, son socket et ses journaux :

instance_archives = http://127.0.0.1:8088
configuration_archives = $ARCH_ETC/haproxy.cfg
unite_archives = pub-epreuve-haproxy-archives.service
socket_archives = /run/pub-epreuve-haproxy-archives.sock

# Etat sain attendu :
#   /  et  /archives/...   application « archives-web »
#   /v2/...                API « archives-api » (/v2/lent met 3 s a repondre)
#   /usurpe/               refuse : c'est un backend qui n'est pas le bon
#   le serveur « degrade » reste hors service
#   une limite de debit existe, et une borne coupe une reponse bloquee
#
# Une panne a ete posee, sans vous dire laquelle. Rendez le livrable :
#   /home/student/incident.yaml
RECETTE
chown student:docker "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

cat > /home/student/README-epreuve <<TXT
EPREUVE HAPROXY : livrer et exploiter deux services.
Duree indicative : 150 minutes. Aucun indice gratuit, aucun corrige.

Deux parties independantes. Le detail de ce qui est attendu est dans
$WORK/recette.txt : lisez-le en entier.

1. LA LIVRAISON, sur edge.lab. HAProxy est installe et n'a aucune mission.
   Deux services (catalogue et notifications) tournent deja, demarres a la
   hate. Publiez-les derriere HAProxy avec routage, HTTPS (un certificat par
   nom, cycle de renouvellement), controle d'acces, limitation, flux long,
   supervision et reprise. Livrables : la configuration de HAProxy, le script
   $WORK/renouveler, le script $WORK/restaurer et la sauvegarde
   $SAUVEGARDE/haproxy.cfg.bak.

2. LA PANNE, sur l'instance « archives » (port 8088). Elle marchait, une
   panne non annoncee l'a atteinte. Diagnostiquez-la, reparez-la sans retirer
   aucune de ses protections, et ecrivez /home/student/incident.yaml :
     famille: routage    # un parmi : routage, sonde, confiance, limite, delai
     composant: "..."
     explication: "..."

Le client independant est poste.lab. La racine de l'autorite de test y est
deposee dans /home/student/racine-acme.pem ; n'utilisez jamais curl -k.
L'autorite de test tire une nouvelle racine a chaque demarrage : la validation
la relit avant chaque verification.
TXT
chown student:student /home/student/README-epreuve

systemctl daemon-reload
systemctl enable pub-epreuve-haproxy-acme.service
systemctl enable --now pub-epreuve-haproxy-catalogue.service
systemctl enable --now pub-epreuve-haproxy-notifications.service
for port in 18301 18302; do
    for _ in $(seq 60); do
        if ss -ltn "sport = :${port}" | grep -q LISTEN; then break; fi
        sleep 1
    done
done

echo "fixture pub-epreuve-haproxy posee"
exit 0
