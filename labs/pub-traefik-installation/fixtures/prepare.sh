#!/usr/bin/env bash
# Pose la situation : une machine propre, Docker installé, mais aucune
# instance Traefik de la mission. Le répertoire de travail porte la
# référence d'image épinglée que l'apprenant doit réutiliser.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-installation.log) 2>&1
set -x

WORK=/opt/pub-installation

docker rm -f pub-installation-traefik 2>/dev/null || true
systemctl stop pub-installation-traefik.service 2>/dev/null || true
systemctl disable pub-installation-traefik.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-installation-traefik.service
systemctl daemon-reload

if timeout 2 bash -c 'exec 3<>/dev/tcp/127.0.0.1/80' 2>/dev/null; then
  echo "Le port 80 est déjà occupé avant la mise en situation." >&2
  exit 1
fi

install -d -m 0775 -o student -g docker "$WORK/dynamic"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic"

docker pull "$IMG_TRAEFIK"
printf '%s\n' "$IMG_TRAEFIK" > "$WORK/image-ref"

cat > "$WORK/README" <<TXT
Répertoire de travail du lab pub-traefik-installation.

Aucune instance Traefik de la mission ne tourne. Installez-en une sous
systemd, fermée par défaut (ni API ni dashboard exposés).

Image retenue, épinglée par digest, à lire dans ce fichier :
  $IMG_TRAEFIK

Faits sur lesquels les tests s'appuient :
  - le nom de service systemd attendu est pub-installation-traefik.service ;
  - le point d'entrée web écoute sur le port 80 de la machine ;
  - la configuration dynamique est lue par le provider fichier, répertoire
    $WORK/dynamic (watch activé) ;
  - les tests comparent la version du conteneur réellement exécuté à la
    référence d'image ci-dessus, pas au contenu d'un fichier.
TXT
chown -R student:docker "$WORK"
echo "Situation posée : machine propre, aucune instance Traefik de la mission."
