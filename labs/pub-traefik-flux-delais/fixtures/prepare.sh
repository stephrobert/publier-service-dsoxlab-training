#!/usr/bin/env bash
# Pose la situation : quatre backends (deux backends API interchangeables,
# un backend de flux WebSocket+SSE, un backend d'action à compteur) et un
# Traefik dont les délais de transport, les délais de réponse du point
# d'entrée, la sonde de santé et la politique de retry sont partiellement
# mal réglés.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-flux.log) 2>&1
set -x

WORK=/opt/pub-flux

if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/80" 2>/dev/null; then
  echo "Le port 80 est déjà occupé avant la mise en situation." >&2
  exit 1
fi

docker rm -f pub-flux-traefik pub-flux-backend-a pub-flux-backend-b \
  pub-flux-backend-flux pub-flux-backend-action 2>/dev/null || true
docker network rm pub-flux 2>/dev/null || true

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic" "$WORK/app"

for _ in $(seq 1 30); do
  if apt-get install -y -qq python3-pip >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
pip3 install --break-system-packages -q 'websockets==17.3'

docker pull "$IMG_TRAEFIK"
docker pull "$IMG_PYTHON"

docker network create --subnet 172.30.11.0/24 pub-flux

cp /tmp/pub-flux-backend_api.py "$WORK/app/backend_api.py"
cp /tmp/pub-flux-backend_action.py "$WORK/app/backend_action.py"
cp /tmp/pub-flux-backend_flux.py "$WORK/app/backend_flux.py"
cp /tmp/pub-flux-mesure_ws.py "$WORK/app/mesure_ws.py"

# --- Deux backends API interchangeables : point testé « retrait ». Les
# deux démarrent sains (fichier /app/healthy présent). ---
for nom in a b; do
  docker run -d --name "pub-flux-backend-$nom" \
    --network pub-flux \
    -v "$WORK/app/backend_api.py:/app/backend_api.py:ro" \
    -w /app \
    "$IMG_PYTHON" python3 backend_api.py
  docker exec "pub-flux-backend-$nom" touch /app/healthy
done

# --- Backend d'action : point testé « post » (critique). Le compteur part
# à 0 et le premier appel POST simule une réponse perdue après écriture
# réussie. ---
docker run -d --name pub-flux-backend-action \
  --network pub-flux \
  -v "$WORK/app/backend_action.py:/app/backend_action.py:ro" \
  -w /app \
  "$IMG_PYTHON" python3 backend_action.py
docker exec pub-flux-backend-action sh -c "echo 0 > /app/compteur"

# --- Backend de flux : point testé « flux ». WebSocket d'écho et flux SSE
# qui émet un événement par seconde, sans délai ni coupure artificiels. ---
docker run -d --name pub-flux-backend-flux \
  --network pub-flux \
  -e WS_PORT=8081 -e SSE_PORT=8080 \
  -v "$WORK/app/backend_flux.py:/app/backend_flux.py:ro" \
  -w /app \
  "$IMG_PYTHON" sh -c "pip install -q 'websockets==17.3' && python3 backend_flux.py"

# --- Configuration dynamique Traefik : volontairement incorrecte sur les
# quatre points testés (délais de transport trop larges, aucune sonde de
# santé, retry appliqué à l'action non idempotente). ---
cat > "$WORK/dynamic/routes.yaml" <<'YAML'
http:
  serversTransports:
    lent:
      forwardingTimeouts:
        dialTimeout: 30s
        responseHeaderTimeout: 30s
  middlewares:
    retry-partout:
      retry:
        attempts: 3
        retryNonIdempotentMethod: true
        status:
          - "500-599"
  routers:
    api:
      rule: Host(`api.flux.lab.test`)
      service: api
    ws:
      rule: Host(`flux.lab.test`) && PathPrefix(`/ws`)
      service: flux-ws
    sse:
      rule: Host(`flux.lab.test`) && PathPrefix(`/events`)
      service: flux-sse
    action:
      rule: Host(`action.flux.lab.test`)
      middlewares:
        - retry-partout
      service: action
  services:
    api:
      loadBalancer:
        serversTransport: lent
        servers:
          - url: http://pub-flux-backend-a:8080
          - url: http://pub-flux-backend-b:8080
    flux-ws:
      loadBalancer:
        servers:
          - url: http://pub-flux-backend-flux:8081
    flux-sse:
      loadBalancer:
        servers:
          - url: http://pub-flux-backend-flux:8080
    action:
      loadBalancer:
        servers:
          - url: http://pub-flux-backend-action:8080
YAML

# --- Configuration statique : délai d'écriture du point d'entrée trop
# court pour un flux SSE qui doit vivre plusieurs secondes. L'inactivité
# (idleTimeout) reste large car aucun flux de ce lab n'a besoin d'être
# borné sur ce point précis. ---
cat > "$WORK/traefik-static.yaml" <<'YAML'
entryPoints:
  web:
    address: ":80"
    transport:
      respondingTimeouts:
        idleTimeout: 120s
        writeTimeout: 3s
providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true
log:
  level: INFO
YAML

docker run -d --name pub-flux-traefik \
  --network pub-flux \
  -p 80:80 \
  -v "$WORK/traefik-static.yaml:/etc/traefik/traefik.yaml:ro" \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  "$IMG_TRAEFIK" --configfile=/etc/traefik/traefik.yaml

# --- Résolution des noms de test, pour que le client WebSocket (qui ne
# connaît pas --resolve) envoie le bon en-tête Host sans jonglage. ---
for nom in api.flux.lab.test flux.lab.test action.flux.lab.test; do
  if ! grep -qE "[[:space:]]$nom\$" /etc/hosts; then
    echo "127.0.0.1 $nom" >> /etc/hosts
  fi
done

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null \
    -H 'Host: api.flux.lab.test' http://127.0.0.1/health 2>/dev/null; then
    break
  fi
  sleep 1
done

cat > "$WORK/README" <<'TXT'
Répertoire de travail du lab pub-traefik-flux-delais.

Traefik écoute sur le port 80 de edge.lab et route par nom d'hôte :

- api.flux.lab.test     : deux backends interchangeables (a, b), route
  /lent?ms=N (lenteur bornée) et /bloque (ne répond jamais) ;
- flux.lab.test/ws      : WebSocket d'écho ;
- flux.lab.test/events  : flux SSE (un événement par seconde) ;
- action.flux.lab.test  : POST /action (compteur), GET /compteur.

Les noms ci-dessus sont déjà résolus en 127.0.0.1 dans /etc/hosts.

À corriger : /opt/pub-flux/dynamic/routes.yaml (transport, sonde de santé,
middleware de retry sur l'action) et /opt/pub-flux/traefik-static.yaml
(délais de réponse du point d'entrée). Un redémarrage du conteneur
pub-flux-traefik est nécessaire après une modification du fichier
statique (`docker restart pub-flux-traefik`) ; le fichier dynamique est
rechargé automatiquement par Traefik.

Pour simuler un backend malade : `docker exec pub-flux-backend-b rm -f
/app/healthy` (et `docker exec pub-flux-backend-b touch /app/healthy`
pour le restaurer). Pour redéclencher la perte de réponse d'une action :
`docker exec pub-flux-backend-action touch /app/couper-une-fois`.
TXT
