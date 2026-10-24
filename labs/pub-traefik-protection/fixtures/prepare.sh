#!/usr/bin/env bash
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-protection.log) 2>&1
set -x

WORK=/opt/pub-admin
docker rm -f pub-admin-baseline 2>/dev/null || true
for port in 443 8080; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
docker pull "$IMG_TRAEFIK"
docker pull "$IMG_SOCKET_PROXY"
printf '%s\n' "$IMG_SOCKET_PROXY" > "$WORK/socket-proxy-image"

ADMIN_PASSWORD="Securite-Lab-2026"
ADMIN_HASH=$(openssl passwd -apr1 -salt pubAdmin2026 "$ADMIN_PASSWORD")
printf 'operator:%s\n' "$ADMIN_HASH" > "$WORK/credentials.htpasswd"
openssl req -x509 -newkey rsa:2048 -nodes -days 2 \
  -keyout "$WORK/admin.key" -out "$WORK/admin.crt" \
  -subj "/CN=admin.lab.test" \
  -addext "subjectAltName=DNS:admin.lab.test"
chmod 0644 "$WORK/admin.crt"
chmod 0600 "$WORK/admin.key"
chmod 0640 "$WORK/credentials.htpasswd"

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Répertoire de travail du lab pub-traefik-protection.

Une instance vulnérable de démonstration expose le tableau de bord et l'API
Traefik directement sur le port 8080. Remplacez-la par une configuration
sécurisée. L'interface attendue est https://admin.lab.test.

Image Traefik disponible, épinglée par digest :
  $IMG_TRAEFIK
Image du proxy de socket Docker, épinglée par digest :
  $IMG_SOCKET_PROXY

Fichiers disponibles :
  - admin.crt : certificat TLS de test pour admin.lab.test ;
  - admin.key : clé privée associée, à ne pas publier.
  - credentials.htpasswd : fichier de test pour l'authentification.

Les tests utilisent le compte de validation "operator" et le mot de passe
"Securite-Lab-2026". Ils appellent /dashboard/ et /api/overview en HTTPS.
L'accès sans identifiants doit être refusé ; l'accès authentifié doit répondre.
Le port direct 8080 doit être fermé. L'accès à l'API Docker doit passer par un
proxy de socket restreint ; le socket ne doit pas être monté dans Traefik.

Le client envoie Host et SNI admin.lab.test à l'adresse locale de la VM.
TXT
chown -R student:docker "$WORK"

docker rm -f pub-admin-baseline 2>/dev/null || true
docker run -d --name pub-admin-baseline \
  -p 8080:8080 \
  "$IMG_TRAEFIK" \
  --api.dashboard=true \
  --api.insecure=true \
  --entrypoints.traefik.address=:8080

for _ in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8080/api/overview >/dev/null; then
    echo "Situation posée : l'API non authentifiée répond sur le port 8080."
    exit 0
  fi
  sleep 1
done
docker logs pub-admin-baseline
echo "L'instance vulnérable ne répond pas sur 8080." >&2
exit 1
