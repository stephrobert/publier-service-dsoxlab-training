#!/usr/bin/env bash
# Pose la situation : deux versions d'un backend (v1 publiée, v2 candidate),
# deux points d'entrée Traefik jumeaux (entry-a, entry-b) qui partagent le
# même répertoire de configuration dynamique et le même certificat TLS, et un
# outil de rotation de certificat non sûr en cas d'exécution concurrente.
#
# LIMITE ASSUMÉE : les deux points d'entrée tournent tous les deux sur
# edge.lab, la seule VM disponible pour ce lab (voir recette). Ils ne
# partagent PAS un hôte dans un sens métaphorique : ils partagent LE MÊME
# hôte réellement, ce qui est précisément ce que le point « edge » demande
# d'observer et de documenter honnêtement, pas de contourner.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-zds.log) 2>&1
set -x

WORK=/opt/pub-zds

for port in 19000 19001; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé ; un lab précédent n'a pas été nettoyé." >&2
    exit 1
  fi
done

docker rm -f pub-zds-entry-a pub-zds-entry-b pub-zds-app-v1 pub-zds-app-v2 \
  2>/dev/null || true
docker network rm pub-zds 2>/dev/null || true

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic" "$WORK/tls" "$WORK/outils" \
  "$WORK/static-a" "$WORK/static-b"

docker pull "$IMG_TRAEFIK"
docker pull "$IMG_PYTHON"

docker network create --subnet 172.30.12.0/24 pub-zds

# --- Deux ports d'hôte fixes pour les deux points d'entrée jumeaux. Fixes
# (pas tirés au hasard) parce que le client poste.lab doit les joindre par
# nom via /etc/hosts, et que deux labs du même type ne tournent jamais en
# parallèle sur edge.lab (règle de la recette). ---
ENTREE_A=19000
ENTREE_B=19001
echo "ENTREE_A=$ENTREE_A
ENTREE_B=$ENTREE_B" > "$WORK/ports.env"

# --- Backends versionnés : v1 et v2 démarrent sains. ---
cp /tmp/pub-zds-backend_version.py "$WORK/backend_version.py"
chmod 0644 "$WORK/backend_version.py"
for v in v1 v2; do
  docker run -d --name "pub-zds-app-$v" \
    --network pub-zds \
    -e "VERSION=$v" \
    -v "$WORK/backend_version.py:/app/backend_version.py:ro" \
    -w /app \
    "$IMG_PYTHON" python3 backend_version.py
done
sleep 1
docker exec pub-zds-app-v1 touch /app/healthy
docker exec pub-zds-app-v2 touch /app/healthy

# --- Certificat TLS partagé initial, servi par les deux points d'entrée. ---
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$WORK/tls/tls.key" -out "$WORK/tls/tls.crt" -days 1 \
  -subj "/CN=zds.lab.test" -addext "subjectAltName=DNS:zds.lab.test"
chmod 0644 "$WORK/tls/tls.crt" "$WORK/tls/tls.key"

# --- Configuration dynamique PARTAGÉE par les deux points d'entrée :
# volontairement câblée en dur sur app-v1 seule, sans service pondéré ni
# sonde de santé. Impossible d'y faire une bascule progressive ni un retrait
# automatique d'une version malsaine en l'état. ---
cat > "$WORK/dynamic/routes.yaml" <<'YAML'
http:
  routers:
    app:
      rule: Host(`zds.lab.test`)
      entryPoints:
        - websecure
      tls: {}
      service: app
  services:
    app:
      loadBalancer:
        servers:
          - url: http://pub-zds-app-v1:8080
tls:
  stores:
    default:
      defaultCertificate:
        certFile: /etc/traefik/certs/tls.crt
        keyFile: /etc/traefik/certs/tls.key
YAML

for nom in a b; do
  cat > "$WORK/static-$nom.yaml" <<YAML
entryPoints:
  websecure:
    address: ":443"
providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true
log:
  level: INFO
YAML
done

docker run -d --name pub-zds-entry-a \
  --network pub-zds \
  -p 0.0.0.0:$ENTREE_A:443 \
  -v "$WORK/static-a.yaml:/etc/traefik/traefik.yaml:ro" \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  -v "$WORK/tls:/etc/traefik/certs:ro" \
  "$IMG_TRAEFIK" --configfile=/etc/traefik/traefik.yaml

docker run -d --name pub-zds-entry-b \
  --network pub-zds \
  -p 0.0.0.0:$ENTREE_B:443 \
  -v "$WORK/static-b.yaml:/etc/traefik/traefik.yaml:ro" \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  -v "$WORK/tls:/etc/traefik/certs:ro" \
  "$IMG_TRAEFIK" --configfile=/etc/traefik/traefik.yaml

# --- Outil de rotation de certificat partagé, remis aux deux points
# d'entrée (représentation locale, hors ligne, du partage non qualifié d'un
# acme.json entre plusieurs instances Traefik : la vraie limite documentée
# par Traefik est qu'un stockage ACME fichier ne tolère pas plusieurs
# écrivains concurrents sans verrou). BOGUÉ À DESSEIN : deux exécutions
# concurrentes peuvent entrelacer leurs écritures de clé et de certificat,
# laissant une paire dépareillée dans $WORK/tls.
cat > "$WORK/outils/tourner-certificat.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
DEST=/opt/pub-zds/tls
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$TMP/tls.key" -out "$TMP/tls.crt" -days 1 \
  -subj "/CN=zds.lab.test" -addext "subjectAltName=DNS:zds.lab.test" \
  2>/dev/null
# BOGUE : deux fichiers séparés, déposés l'un après l'autre sans verrou ni
# écriture atomique groupée, et dans un ordre qui varie d'une exécution à
# l'autre. Quand deux exécutions concurrentes choisissent un ordre
# différent (l'une dépose le certificat puis la clé, l'autre la clé puis le
# certificat), leurs écritures s'entrelacent et la dernière à toucher
# chaque fichier n'est pas forcément la même exécution : la paire finale
# peut être dépareillée.
if (( RANDOM % 2 == 0 )); then
  cp "$TMP/tls.crt" "$DEST/tls.crt"
  sleep "0.$(( RANDOM % 5 + 1 ))"
  cp "$TMP/tls.key" "$DEST/tls.key"
else
  cp "$TMP/tls.key" "$DEST/tls.key"
  sleep "0.$(( RANDOM % 5 + 1 ))"
  cp "$TMP/tls.crt" "$DEST/tls.crt"
fi
SH
chmod 0755 "$WORK/outils/tourner-certificat.sh"
chown -R student:docker "$WORK"

for _ in $(seq 1 30); do
  if curl -sk --resolve zds.lab.test:$ENTREE_A:127.0.0.1 \
    "https://zds.lab.test:$ENTREE_A/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cat > "$WORK/README" <<TXT
Répertoire de travail du lab pub-traefik-zero-downtime.

Deux points d'entrée Traefik jumeaux tournent sur edge.lab :
  entry-a : port $ENTREE_A (hôte)
  entry-b : port $ENTREE_B (hôte)
Les deux lisent la MÊME configuration dynamique ($WORK/dynamic/routes.yaml)
et SERVENT LE MÊME certificat partagé ($WORK/tls).

Deux versions du backend tournent déjà, toutes deux saines :
  pub-zds-app-v1 (en production, seule servie actuellement)
  pub-zds-app-v2 (candidate)
Chacune répond "version=v1" ou "version=v2" sur /, et expose /health
(200 si /app/healthy existe dans le conteneur, 503 sinon). Retirer le
fichier /app/healthy d'une version simule une panne réelle de cette
version : ses requêtes passent alors en 500, pas seulement sa sonde.

Outil fourni : $WORK/outils/tourner-certificat.sh, qui régénère le
certificat partagé. Il est volontairement dangereux en cas d'appel
concurrent : c'est le point à corriger pour « certificats ».
TXT
chown student:docker "$WORK/README"
