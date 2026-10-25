#!/usr/bin/env bash
# Pose la situation : quatre backends whoami, un réseau Docker partagé, et un
# Traefik dont les priorités, le périmètre et les références inter-provider
# sont partiellement mal réglés.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-routage.log) 2>&1
set -x

WORK=/opt/pub-routage

if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/80' 2>/dev/null; then
  echo "Le port 80 est déjà occupé avant la mise en situation." >&2
  exit 1
fi

docker rm -f pub-routage-traefik pub-routage-api-v1 pub-routage-api-v2 \
  pub-routage-admin pub-routage-catalogue 2>/dev/null || true
docker network rm pub-routage 2>/dev/null || true

install -d -m 0775 -o student -g docker "$WORK/dynamic"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic"

docker pull "$IMG_TRAEFIK"
docker pull "$IMG_WHOAMI"

docker network create pub-routage

docker run -d --name pub-routage-api-v1 --network pub-routage \
  --hostname api-v1 "$IMG_WHOAMI"
docker run -d --name pub-routage-api-v2 --network pub-routage \
  --hostname api-v2 "$IMG_WHOAMI"
docker run -d --name pub-routage-admin --network pub-routage \
  --hostname admin "$IMG_WHOAMI"
docker run -d --name pub-routage-catalogue --network pub-routage \
  --hostname catalogue \
  --label traefik.enable=true \
  --label traefik.docker.network=pub-routage \
  --label traefik.http.services.cible.loadbalancer.server.port=80 \
  --label traefik.http.middlewares.marque.headers.customresponseheaders.X-Marque=docker \
  "$IMG_WHOAMI"

cat > "$WORK/dynamic/routes.yaml" <<'YAML'
http:
  routers:
    api-v1-defaut:
      rule: Host(`routage.lab.test`)
      entryPoints:
        - web
      service: api-v1
      priority: 100
    api-v2:
      rule: Host(`routage.lab.test`) && PathPrefix(`/v2`)
      entryPoints:
        - web
      service: api-v2
      priority: 10
    admin:
      rule: PathPrefix(`/admin`)
      entryPoints:
        - web
      service: admin
      priority: 50
    catalogue:
      rule: Host(`catalogue.routage.lab.test`)
      entryPoints:
        - web
      service: cible
      middlewares:
        - marque
      priority: 50
  services:
    api-v1:
      loadBalancer:
        servers:
          - url: http://api-v1:80
    api-v2:
      loadBalancer:
        servers:
          - url: http://api-v2:80
    admin:
      loadBalancer:
        servers:
          - url: http://admin:80
    cible:
      loadBalancer:
        servers:
          - url: http://127.0.0.1:1
  middlewares:
    marque:
      headers:
        customResponseHeaders:
          X-Marque: fichier
YAML

docker run -d --name pub-routage-traefik \
  --network pub-routage \
  -p 80:80 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  "$IMG_TRAEFIK" \
  --entrypoints.web.address=:80 \
  --providers.file.directory=/etc/traefik/dynamic \
  --providers.file.watch=true \
  --providers.docker=true \
  --providers.docker.exposedByDefault=false \
  --providers.docker.network=pub-routage \
  --log.level=INFO

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null \
    --write-out '%{http_code}' -H 'Host: routage.lab.test' http://127.0.0.1/ | grep -qE '^(200|502|504)$'; then
    break
  fi
  sleep 1
done

cat > "$WORK/README" <<'TXT'
Répertoire de travail du lab pub-traefik-routage.

Traefik lit sa configuration dynamique dans /opt/pub-routage/dynamic/
(provider fichier) et découvre le conteneur "catalogue" étiqueté sur le
réseau Docker "pub-routage" (provider Docker, service et middleware nommés
"cible" et "marque"). Chaque backend whoami répond avec son propre
"Hostname:" et, pour le catalogue, le middleware attendu ajoute un en-tête
"X-Marque: docker" à la réponse.

La configuration actuelle est mal réglée :
  - le routeur générique (Host routage.lab.test) a une priorité trop haute et
    empêche /v2 d'atteindre l'API v2 ;
  - le panneau d'administration n'a pas de condition d'hôte : il répond
    depuis n'importe quel nom, pas seulement routage.lab.test ;
  - le routeur catalogue référence un service et un middleware du même nom
    dans le provider fichier (non qualifiés), au lieu des objets réels
    publiés par le provider Docker.

Corrigez /opt/pub-routage/dynamic/routes.yaml. Les tests appellent le
véritable point d'entrée HTTP sur le port 80 et lisent le corps et les
en-têtes de la réponse.
TXT
chown -R student:docker "$WORK"
echo "Situation posée : quatre backends whoami actifs, Traefik actif, routage mal réglé."
