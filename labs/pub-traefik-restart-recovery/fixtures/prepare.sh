#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-restart.log) 2>&1
set -x

WORK=/opt/pub-restart
docker rm -f pub-restart-whoami 2>/dev/null || true
if [[ -f "$WORK/compose.yaml" ]] || [[ -f "$WORK/compose.yml" ]]; then
  (cd "$WORK" && docker compose down -v --remove-orphans) || true
fi
install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
docker pull "$IMG_WHOAMI"
printf '%s\n' "$IMG_WHOAMI" > "$WORK/image-ref"

cat > "$WORK/README" <<TXT
Répertoire de travail du lab pub-traefik-restart-recovery.

Écrivez ici votre compose.yaml pour lancer le service whoami sur le port
18080 de edge.lab. L'image est déjà tirée et épinglée par digest :
  $IMG_WHOAMI

Le service doit répondre en HTTP sur http://edge.lab:18080/ avant et après
un redémarrage du moteur Docker. Les tests redémarrent le moteur une fois.
TXT
chown -R student:docker "$WORK"

if ss -ltnH 'sport = :18080' | grep -q .; then
  echo "Le port 18080 est déjà occupé avant la mise en situation." >&2
  exit 1
fi
echo "Situation posée : le répertoire de travail est vide et le port 18080 libre."
