#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-traefik-acme.log) 2>&1
set -x

WORK=/opt/pub-traefik-acme

for port in 80 443 14000 15000; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé ; un lab précédent n'a pas été nettoyé." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic"

for image in "$IMG_TRAEFIK" "$IMG_WHOAMI" "$IMG_PEBBLE" "$IMG_CHALLTESTSRV"; do
  docker pull "$image"
done

docker network rm acme-renewal 2>/dev/null || true
docker network create --driver bridge --subnet 172.29.0.0/24 \
  --gateway 172.29.0.1 acme-renewal

docker create --name pub-renewal-config "$IMG_PEBBLE"
docker cp pub-renewal-config:/test/config/pebble-config.json "$WORK/pebble-config.json"
docker cp pub-renewal-config:/test/certs/pebble.minica.pem "$WORK/pebble.minica.pem"
docker rm pub-renewal-config

python3 - "$WORK/pebble-config.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as config_file:
    config = json.load(config_file)
config["pebble"]["httpPort"] = 80
config["pebble"]["profiles"]["default"]["validityPeriod"] = 300
config["pebble"]["profiles"]["shortlived"]["validityPeriod"] = 300
with open(sys.argv[1], "w", encoding="utf-8") as config_file:
    json.dump(config, config_file, indent=2)
    config_file.write("\n")
PY
chmod 0644 "$WORK/pebble-config.json" "$WORK/pebble.minica.pem"

cat > "$WORK/platform.yaml" <<YAML
services:
  challtestsrv:
    image: $IMG_CHALLTESTSRV
    container_name: pub-renewal-challtestsrv
    command: ["-defaultIPv6", "", "-defaultIPv4", "172.29.0.1"]
    networks: [acme-renewal]
  pebble:
    image: $IMG_PEBBLE
    container_name: pub-renewal-pebble
    command: ["-config", "/test/config/pebble-config.json", "-dnsserver", "pub-renewal-challtestsrv:8053"]
    environment:
      PEBBLE_VA_NOSLEEP: "1"
    ports:
      - "127.0.0.1:14000:14000"
      - "127.0.0.1:15000:15000"
    volumes:
      - ./pebble-config.json:/test/config/pebble-config.json:ro
    depends_on: [challtestsrv]
    networks:
      acme-renewal:
        aliases: [pebble]
networks:
  acme-renewal:
    external: true
YAML
chown -R student:docker "$WORK"

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Répertoire de travail du lab pub-traefik-acme.

L'autorité Pebble et son résolveur de défis tournent déjà via platform.yaml.
Construisez votre Compose dans compose.yaml. Le service à publier est
app.lab.test en HTTPS sur le port 443 ; le défi ACME HTTP utilise le port 80.

Images disponibles, épinglées par digest :
  Traefik : $IMG_TRAEFIK
  whoami  : $IMG_WHOAMI

Faits observables :
  - l'annuaire ACME est https://pebble:14000/dir depuis le réseau Docker
    acme-renewal ;
  - Pebble sert sa racine et son intermédiaire sur l'API de gestion
    https://localhost:15000/roots/0 et /intermediates/0 ;
  - pebble.minica.pem authentifie le serveur HTTPS de Pebble ; ce n'est pas une
    autorité publique ni la clé d'une application ;
  - pebble-root.pem est la racine courante qui signe les certificats ACME
    remis pendant cette session ;
  - app.lab.test résout vers la passerelle Docker 172.29.0.1 pour le défi ;
  - les profils ACME de cette autorité de test émettent des certificats valides
    5 minutes, uniquement pour rendre le renouvellement observable rapidement ;
  - les ports 80 et 443 sont réservés à Traefik ; 14000 et 15000 sont publiés
    uniquement sur localhost.

Le client de validation envoie Host/SNI app.lab.test à 127.0.0.1. La
configuration dynamique TLS se place dans le répertoire dynamic/.
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

docker compose -f "$WORK/platform.yaml" up -d
for _ in $(seq 1 30); do
  if curl -skf https://localhost:14000/dir >/dev/null; then
    curl -skf https://localhost:15000/roots/0 -o "$WORK/pebble-root.pem"
    chown student:docker "$WORK/pebble-root.pem"
    echo "Pebble répond ; le poste est prêt."
    exit 0
  fi
  sleep 1
done
docker compose -f "$WORK/platform.yaml" logs
echo "Pebble n'a pas répondu sur localhost:14000." >&2
exit 1
