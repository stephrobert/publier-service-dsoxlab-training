#!/usr/bin/env bash
# Pose la situation : un répertoire de travail vide, les images tirées, le
# réseau pub-lab et le conteneur témoin pub-interne (sans étiquette Traefik).
set -euo pipefail
exec > >(tee /var/log/dsoxlab-prepare.log) 2>&1
set -x

TRAVAIL=/opt/pub-lab

if [[ -f "$TRAVAIL/compose.yaml" ]] || [[ -f "$TRAVAIL/compose.yml" ]]; then
  (cd "$TRAVAIL" && docker compose down -v --remove-orphans) || true
fi
# Le filtre `ancestor` ne retrouve pas une image tirée par digest : on lit le
# nom d'image affiché par `docker ps`.
for id in $(docker ps -a --format '{{.ID}} {{.Image}}' | awk '$2 ~ /^traefik(\/whoami)?[:@]/ {print $1}'); do docker rm -f "$id" || true; done
docker network rm pub-lab 2>/dev/null || true
install -d -m 0775 -o student -g docker "$TRAVAIL"
find "$TRAVAIL" -mindepth 1 -delete

for img in "$IMG_TRAEFIK" "$IMG_WHOAMI"; do
  docker pull "$img"
done

docker network create pub-lab
docker run -d --name pub-interne --network pub-lab "$IMG_WHOAMI"

cat > "$TRAVAIL/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-traefik-docker.

Écrivez ici votre compose.yaml : Traefik devant DEUX instances de whoami,
joignables sous le nom whoami.lab.test sur le port 80 de la machine.

Les images sont déjà tirées, épinglées par digest :
TXT
{ echo "  $IMG_TRAEFIK"; echo "  $IMG_WHOAMI"; } >> "$TRAVAIL/LISEZ-MOI.txt"
cat >> "$TRAVAIL/LISEZ-MOI.txt" <<'TXT'

Faits sur lesquels les tests s'appuient :
  - le réseau Docker "pub-lab" existe déjà (déclarez-le external dans le
    Compose) ; le conteneur "pub-interne" y tourne, sans étiquette Traefik, et
    doit rester injoignable par Traefik ;
  - les tests envoient "Host: whoami.lab.test" sur http://127.0.0.1:80 ;
  - whoami répond sur /health (200 tant qu'on ne l'a pas rendu malade) ;
  - Traefik lit le socket Docker, monté en lecture seule.
TXT
chown student:docker "$TRAVAIL/LISEZ-MOI.txt"

if ss -ltnH 'sport = :80' | grep -q .; then
  echo "Le port 80 répond déjà : un service hérité n'a pas été retiré." >&2
  exit 1
fi
echo "Situation posée : $TRAVAIL est vide, pub-interne tourne, rien n'écoute sur 80."
