#!/usr/bin/env bash
# Pose la situation : deux backends whoami distincts, un réseau Docker partagé,
# et un Traefik dont la configuration dynamique mélange les associations.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-modele.log) 2>&1
set -x

WORK=/opt/pub-modele

if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/80' 2>/dev/null; then
  echo "Le port 80 est déjà occupé avant la mise en situation." >&2
  exit 1
fi

docker rm -f pub-modele-traefik pub-modele-app-a pub-modele-app-b 2>/dev/null || true
docker network rm pub-modele 2>/dev/null || true

install -d -m 0775 -o student -g docker "$WORK/dynamic"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic"

docker pull "$IMG_TRAEFIK"
docker pull "$IMG_WHOAMI"

docker network create pub-modele

docker run -d --name pub-modele-app-a --network pub-modele \
  --hostname app-a "$IMG_WHOAMI"

docker run -d --name pub-modele-app-b --network pub-modele \
  --hostname app-b \
  --label traefik.enable=true \
  --label traefik.docker.network=pub-modele \
  --label traefik.http.services.cible.loadbalancer.server.port=80 \
  "$IMG_WHOAMI"

cat > "$WORK/dynamic/routes.yaml" <<'YAML'
http:
  routers:
    modele-a:
      rule: Host(`modele-a.lab.test`)
      entryPoints:
        - web
      service: cible
    modele-b:
      rule: Host(`modele-b.lab.test`)
      entryPoints:
        - web
      service: cible
    attrape-tout:
      rule: PathPrefix(`/`)
      entryPoints:
        - web
      service: app-a
      priority: 1
  services:
    app-a:
      loadBalancer:
        servers:
          - url: http://app-a:80
    cible:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:1
YAML

docker run -d --name pub-modele-traefik \
  --network pub-modele \
  -p 80:80 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  "$IMG_TRAEFIK" \
  --entrypoints.web.address=:80 \
  --providers.file.directory=/etc/traefik/dynamic \
  --providers.file.watch=true \
  --providers.docker=true \
  --providers.docker.exposedByDefault=false \
  --providers.docker.network=pub-modele \
  --log.level=INFO

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null \
    --write-out '%{http_code}' -H 'Host: modele-a.lab.test' http://127.0.0.1/ | grep -qE '^(200|502|504)$'; then
    break
  fi
  sleep 1
done

started_at=$(docker inspect --format '{{.State.StartedAt}}' pub-modele-traefik)
printf '%s\n' "$started_at" > "$WORK/traefik-started-at"
cat > "$WORK/README" <<'TXT'
Répertoire de travail du lab pub-traefik-modele.

Traefik tourne déjà. Il lit sa configuration dynamique dans
/opt/pub-modele/dynamic/ (provider fichier) et découvre les conteneurs
étiquetés sur le réseau Docker "pub-modele" (provider Docker).

Deux backends whoami tournent déjà : "app-a" (atteignable uniquement par
adresse directe dans le provider fichier) et "app-b" (étiqueté pour le
provider Docker sous le nom de service "cible"). Chaque backend répond avec
son propre "Hostname:" dans le corps.

La configuration actuelle est mal reliée : modele-a.lab.test et
modele-b.lab.test pointent tous deux vers le même service injoignable, et un
routeur sans condition de nom répond à la place de tout hôte non prévu.
Corrigez /opt/pub-modele/dynamic/routes.yaml. Les tests appellent le
véritable point d'entrée HTTP sur le port 80 et lisent le corps de la réponse.
TXT
chown -R student:docker "$WORK"
echo "Situation posée : deux backends whoami actifs, Traefik actif, routage mal relié."
