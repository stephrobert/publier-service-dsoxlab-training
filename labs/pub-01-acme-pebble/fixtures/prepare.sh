#!/usr/bin/env bash
# Pose la situation : un répertoire de travail vide, les images déjà tirées,
# et rien qui tourne. Les images sont tirées ICI pour que le temps du lab ne
# soit pas du temps de téléchargement.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-prepare.log) 2>&1
set -x

TRAVAIL=/opt/pub-lab

if [[ -f "$TRAVAIL/compose.yaml" ]] || [[ -f "$TRAVAIL/compose.yml" ]]; then
  (cd "$TRAVAIL" && docker compose down -v --remove-orphans) || true
fi
for img in ghcr.io/letsencrypt/pebble ghcr.io/letsencrypt/pebble-challtestsrv goacme/lego; do
  for id in $(docker ps -aq --filter "ancestor=$img" 2>/dev/null); do docker rm -f "$id" || true; done
done
install -d -m 0775 -o student -g docker "$TRAVAIL"
find "$TRAVAIL" -mindepth 1 -delete

for img in "$IMG_PEBBLE" "$IMG_CHALLTESTSRV" "$IMG_LEGO"; do
  docker pull "$img"
done

cat > "$TRAVAIL/LISEZ-MOI.txt" <<'TXT'
Répertoire de travail du lab pub-01-acme-pebble.

Écrivez ici votre compose.yaml (Pebble et pebble-challtestsrv), puis obtenez
un certificat pour le nom app.lab.test avec lego, en HTTP-01.

Les images sont déjà tirées, épinglées par digest :
TXT
{ echo "  $IMG_PEBBLE"; echo "  $IMG_CHALLTESTSRV"; echo "  $IMG_LEGO"; } >> "$TRAVAIL/LISEZ-MOI.txt"
cat >> "$TRAVAIL/LISEZ-MOI.txt" <<'TXT'

Chemins que les tests lisent (ils interrogent Pebble, pas vos fichiers) :
  - l'annuaire ACME de Pebble répond sur https://localhost:14000/dir ;
  - son API de gestion répond sur https://localhost:15000 ;
  - lego écrit ses fichiers sous /opt/pub-lab/lego (option --path) : le
    certificat sera /opt/pub-lab/lego/certificates/app.lab.test.crt.
TXT
chown student:docker "$TRAVAIL/LISEZ-MOI.txt"

for port in 14000 15000 5002; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port répond déjà : un service hérité n'a pas été retiré." >&2
    exit 1
  fi
done
echo "Situation posée : $TRAVAIL est vide, rien n'écoute sur 14000, 15000 ni 5002."
