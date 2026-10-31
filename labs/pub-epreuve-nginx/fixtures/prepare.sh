#!/usr/bin/env bash
# Pose le banc de l'épreuve pub-epreuve-nginx sur edge.lab.
#
# CE QUI EXISTE QUAND L'APPRENANT ARRIVE
#   - Nginx est installé (par le setup, depuis nginx.org) mais ne sert rien :
#     aucune configuration, service arrêté ET désactivé.
#   - Une autorité ACME de test (Pebble) et son serveur de défis, un client
#     ACME (lego) en image épinglée déjà tirée.
#   - Un site statique à publier, une API sur la boucle locale (service
#     systemd), un fichier de mots de passe pour /admin.
#   - Un incident tiré au sort, qui sera posé APRÈS la recette initiale.
#
# CE QUI N'EXISTE PAS : aucune configuration Nginx, aucun certificat,
# aucune sauvegarde, aucune alerte.
set -euo pipefail
# Le journal du setup est illisible pour l'apprenant : le tirage de l'incident
# n'y apparait pas, la trace (`set -x`) est coupee avant ce point.
install -m 0600 /dev/null /var/log/dsoxlab-pub-epreuve-nginx.log
exec > >(tee /var/log/dsoxlab-pub-epreuve-nginx.log) 2>&1
set -x

WORK=/opt/pub-epreuve-nginx
STATE=/var/lib/pub-epn
CACHE=/root/.pub-epn
SECRET=/root/.pub-epn-secret.yaml

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl ca-certificates openssl

# --- Remise à zéro : le banc se rejoue à l'identique ----------------------
systemctl disable --now nginx.service 2>/dev/null || true
systemctl disable --now pub-epn-incident.path pub-epn-api.service 2>/dev/null || true
rm -rf /etc/systemd/system/pub-epn-api.service.d
find /etc/nginx/conf.d -mindepth 1 -delete 2>/dev/null || true
docker rm -f pub-epn-pebble pub-epn-challtestsrv 2>/dev/null || true
rm -rf "$WORK" "$STATE" "$CACHE" /var/backups/pub-epn
rm -f /usr/local/bin/renouveler-certificats /usr/local/bin/sauvegarder-service \
  /usr/local/bin/restaurer-service /usr/local/bin/sonde-alerte \
  /home/student/recette-initiale.md /home/student/incident.yaml
install -d -m 0775 -o student -g docker "$WORK"
install -d -m 0775 -o student -g docker "$WORK/lego" "$WORK/defi"
install -d -m 0755 "$STATE"
install -d -m 0700 "$CACHE"

aleatoire() {
  # `head` en tête de tube : lire /dev/urandom par `tr` jusqu'à ce que
  # `head` ferme le tube tuerait `tr` par SIGPIPE sous pipefail.
  head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
}

# --- Autorité ACME de test et client --------------------------------------
for img in "$IMG_PEBBLE" "$IMG_CHALLTESTSRV" "$IMG_LEGO"; do
  docker pull "$img"
done

# La racine qui signe l'API de Pebble n'est pas celle qui signe les
# certificats émis : on récupère la première ici, sans exécuter l'image
# (elle est distroless).
docker rm -f pub-epn-extraction 2>/dev/null || true
docker create --name pub-epn-extraction "$IMG_PEBBLE" >/dev/null
docker cp pub-epn-extraction:/test/certs/pebble.minica.pem "$WORK/lego/pebble.minica.pem"
docker rm -f pub-epn-extraction >/dev/null
chmod 0644 "$WORK/lego/pebble.minica.pem"
chown student:docker "$WORK/lego/pebble.minica.pem"
printf '%s\n' "$IMG_LEGO" > "$WORK/image-lego.txt"
chmod 0644 "$WORK/image-lego.txt"

cat > "$WORK/pebble.json" <<'JSON'
{
  "pebble": {
    "listenAddress": "0.0.0.0:14000",
    "managementListenAddress": "0.0.0.0:15000",
    "certificate": "test/certs/localhost/cert.pem",
    "privateKey": "test/certs/localhost/key.pem",
    "httpPort": 80,
    "tlsPort": 443,
    "ocspResponderURL": "",
    "externalAccountBindingRequired": false
  }
}
JSON

cat > "$WORK/compose.yaml" <<YAML
services:
  pebble:
    image: "$IMG_PEBBLE"
    container_name: pub-epn-pebble
    network_mode: host
    restart: unless-stopped
    environment:
      PEBBLE_VA_NOSLEEP: "1"
      PEBBLE_WFE_NONCEREJECT: "0"
    volumes:
      - ./pebble.json:/test/config/pebble-config.json:ro
    command: ["-config", "/test/config/pebble-config.json", "-dnsserver", "127.0.0.1:8053"]
  challtestsrv:
    image: "$IMG_CHALLTESTSRV"
    container_name: pub-epn-challtestsrv
    network_mode: host
    restart: unless-stopped
    command: ["-dnsserver", ":8053", "-defaultIPv6", "", "-http01", "", "-https01", "", "-tlsalpn01", "", "-management", ":8055"]
YAML
chown student:docker "$WORK/pebble.json" "$WORK/compose.yaml"
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" up -d

for nom in www.epreuve.test api.epreuve.test; do
  grep -q " $nom\$" /etc/hosts || echo "127.0.0.1 $nom" >> /etc/hosts
  curl -s -X POST -d "{\"host\":\"$nom\",\"addresses\":[\"127.0.0.1\"]}" \
    http://127.0.0.1:8055/add-a || true
done

set +x

# --- Le site statique à publier -------------------------------------------
TOKEN_SITE=$(aleatoire 8)
TOKEN_APROPOS=$(aleatoire 8)
TOKEN_ENV=$(aleatoire 8)
install -d -m 0755 "$WORK/site" "$WORK/site/assets" "$WORK/site/.git"
cat > "$WORK/site/index.html" <<HTML
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Catalogue</title></head>
<body><h1>Catalogue</h1><p>repere-site-$TOKEN_SITE</p></body></html>
HTML
cat > "$WORK/site/apropos.html" <<HTML
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>A propos</title></head>
<body><h1>A propos</h1><p>repere-apropos-$TOKEN_APROPOS</p></body></html>
HTML
printf 'body { font-family: sans-serif; }\n' > "$WORK/site/assets/app.css"
printf 'CLE_SECRETE=fuite-env-%s\n' "$TOKEN_ENV" > "$WORK/site/.env"
printf 'ref: refs/heads/main\n# fuite-git-%s\n' "$TOKEN_ENV" > "$WORK/site/.git/HEAD"
chown -R root:root "$WORK/site"
find "$WORK/site" -type d -exec chmod 0755 {} +
find "$WORK/site" -type f -exec chmod 0644 {} +

# --- L'API, et son unité systemd ------------------------------------------
install -m 0644 /tmp/pub-epn-api.py "$WORK/api.py"
API_SHA=$(sha256sum "$WORK/api.py" | cut -d' ' -f1)
VALEUR=$(( (RANDOM % 9000) + 1000 ))
printf '{"valeur": %s}\n' "$VALEUR" > "$STATE/donnees.json"
MARQUEUR_ALPHA=$(aleatoire 8)
MARQUEUR_BETA=$(aleatoire 8)
printf '%s\n' "$MARQUEUR_ALPHA" > "$STATE/marqueur-alpha.txt"
printf '%s\n' "$MARQUEUR_BETA" > "$STATE/marqueur-beta.txt"
SECRET_ADMIN=$(aleatoire 8)
printf '%s\n' "$SECRET_ADMIN" > "$STATE/secret-admin.txt"
chmod 0644 "$STATE"/*.txt "$STATE/donnees.json"

cat > /etc/systemd/system/pub-epn-api.service <<UNIT
[Unit]
Description=API catalogue (epreuve pub-epreuve-nginx)
After=network.target

[Service]
Environment=PORT=18201 ADRESSE=127.0.0.1 DONNEES=$STATE
RuntimeDirectory=pub-epn
ExecStart=/usr/bin/python3 $WORK/api.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

# --- Mots de passe de /admin ----------------------------------------------
ADMIN_UTILISATEUR=exploitation
ADMIN_MOT_DE_PASSE=$(aleatoire 9)
printf '%s:%s\n' "$ADMIN_UTILISATEUR" "$(openssl passwd -apr1 "$ADMIN_MOT_DE_PASSE")" \
  > "$WORK/admin.htpasswd"
chmod 0644 "$WORK/admin.htpasswd"

# --- Incident : certificat périmé de rechange, script, tirage -------------
# Un certificat à la fois périmé et signé par lui-même, pour les deux noms.
# `openssl ca -selfsign` accepte des dates passées, ce que `req -days` ne
# permet pas, sans dépendre de la version d'OpenSSL.
install -d -m 0700 "$CACHE/ca"
: > "$CACHE/ca/index.txt"
printf '01\n' > "$CACHE/ca/serial"
cat > "$CACHE/ca/ca.cnf" <<CNF
[ca]
default_ca = ca_def
[ca_def]
dir = $CACHE/ca
database = $CACHE/ca/index.txt
new_certs_dir = $CACHE/ca
serial = $CACHE/ca/serial
default_md = sha256
policy = pol
unique_subject = no
x509_extensions = ext
[pol]
commonName = supplied
[ext]
basicConstraints = CA:FALSE
subjectAltName = DNS:www.epreuve.test,DNS:api.epreuve.test
CNF
openssl genrsa -out "$CACHE/expire.key" 2048
openssl req -new -key "$CACHE/expire.key" -subj "/CN=www.epreuve.test" \
  -out "$CACHE/expire.csr"
openssl ca -config "$CACHE/ca/ca.cnf" -selfsign -keyfile "$CACHE/expire.key" \
  -in "$CACHE/expire.csr" -out "$CACHE/expire.crt" \
  -startdate 20230101000000Z -enddate 20230102000000Z -batch -notext
chmod 0600 "$CACHE/expire.key" "$CACHE/expire.crt"

install -m 0700 /tmp/pub-epn-injecter.sh "$CACHE/injecter.sh"
cat > /etc/systemd/system/pub-epn-incident.service <<UNIT
[Unit]
Description=Incident de l'epreuve pub-epreuve-nginx (pose apres la recette)

[Service]
Type=oneshot
ExecStart=$CACHE/injecter.sh
UNIT
cat > /etc/systemd/system/pub-epn-incident.path <<UNIT
[Unit]
Description=Surveille la recette initiale de l'epreuve pub-epreuve-nginx

[Path]
PathChanged=/home/student/recette-initiale.md

[Install]
WantedBy=multi-user.target
UNIT

INCIDENT=$(shuf -e amont tls droits entetes -n 1)

cat > "$SECRET" <<YAML
incident: $INCIDENT
admin_utilisateur: $ADMIN_UTILISATEUR
admin_mot_de_passe: "$ADMIN_MOT_DE_PASSE"
secret_admin: "$SECRET_ADMIN"
repere_site: "repere-site-$TOKEN_SITE"
repere_apropos: "repere-apropos-$TOKEN_APROPOS"
fuite_env: "fuite-env-$TOKEN_ENV"
valeur: $VALEUR
marqueur_alpha: "$MARQUEUR_ALPHA"
marqueur_beta: "$MARQUEUR_BETA"
api_sha256: "$API_SHA"
YAML
chmod 0600 "$SECRET"

systemctl daemon-reload
systemctl enable --now pub-epn-api.service
systemctl enable --now pub-epn-incident.path

# --- Consignes pour l'apprenant -------------------------------------------
cat > "$WORK/LISEZ-MOI.txt" <<TXT
Le banc de l'epreuve Nginx.

  noms a publier       : www.epreuve.test (site) et api.epreuve.test (API)
  resolution           : aucun DNS. Depuis poste.lab, utilisez
                         curl --resolve <nom>:443:<IP de edge.lab>
  contenu du site      : $WORK/site (publiez-le TEL QUEL, ne le copiez pas)
  API                  : 127.0.0.1:18201, service systemd pub-epn-api
  mots de passe /admin : $WORK/admin.htpasswd, utilisateur
                         $ADMIN_UTILISATEUR, mot de passe dans
                         /home/student/README-epreuve
  autorite ACME locale : https://localhost:14000/dir
  gestion de Pebble    : https://localhost:15000 (racine : /roots/0)
  autorite de son API  : $WORK/lego/pebble.minica.pem
  client ACME          : l'image reference dans $WORK/image-lego.txt
  compte et certificats: $WORK/lego (le compte ACME vit sous
                         $WORK/lego/accounts, ne l'effacez pas)
  repertoire du defi   : $WORK/defi (webroot HTTP-01)

La racine de Pebble change a chaque demarrage de l'autorite, c'est voulu.
La recuperer, jamais la supposer.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

cat > /home/student/README-epreuve <<TXT
EPREUVE NGINX : publier et exploiter un service

Banc decrit dans $WORK/LISEZ-MOI.txt (sur edge.lab).
Utilisateur de /admin : $ADMIN_UTILISATEUR
Mot de passe          : $ADMIN_MOT_DE_PASSE

Livrables, sur edge.lab :
  /usr/local/bin/renouveler-certificats   renouvelle ET met en service
  /usr/local/bin/sauvegarder-service      sauvegarde ce qui permet de revenir
  /usr/local/bin/restaurer-service        restaure depuis cette sauvegarde
  /usr/local/bin/sonde-alerte             code 0 si sain, non nul sinon
  /var/log/nginx/epreuve.json             journal d'acces JSON
  127.0.0.1:8081/nginx_status             stub_status, boucle locale seule
  /home/student/recette-initiale.md       compte rendu de votre recette
  /home/student/incident.yaml             couche, composant, explication

Ecrire recette-initiale.md declenche l'incident : faites-le quand votre
recette initiale est passee, pas avant.
TXT
chown student:student /home/student/README-epreuve

# --- Preuve que le banc est sain avant tout travail -----------------------
for _ in $(seq 1 30); do
  code_api=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18201/v1/valeur || true)
  [[ "$code_api" == 200 ]] && break
  sleep 1
done
[[ "$code_api" == 200 ]]

for _ in $(seq 1 60); do
  if curl --max-time 3 --silent --output /dev/null -k https://127.0.0.1:14000/dir; then
    echo "Banc posé : autorité de test et API en marche, Nginx ne sert rien."
    exit 0
  fi
  sleep 2
done
docker compose --project-directory "$WORK" -f "$WORK/compose.yaml" logs
echo "Pebble ne répond pas." >&2
exit 1
