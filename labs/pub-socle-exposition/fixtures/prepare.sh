#!/usr/bin/env bash
# Pose la situation : un point d'entrée, un backend et une administration qui
# écoutent tous les trois sur toutes les interfaces, donc joignables du client.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-exposition.log) 2>&1
set -x

for u in pub-expo-public pub-expo-backend pub-expo-admin; do
  systemctl stop "$u.service" 2>/dev/null || true
done

install -d -m 0755 /opt/pub-expo /etc/pub-expo
install -m 0644 /tmp/pub-socle-exposition-app.py /opt/pub-expo/app.py

# Ports tirés au hasard : une matrice recopiée d'un autre poste ne passe pas.
mapfile -t PORTS < <(shuf -i 18600-18899 -n 3)
PUBLIC=${PORTS[0]}
BACKEND=${PORTS[1]}
ADMIN=${PORTS[2]}

echo "PUBLIC=$PUBLIC
BACKEND=$BACKEND
ADMIN=$ADMIN" > /etc/pub-expo/ports.env

cat > /etc/pub-expo/public.env <<ENV
ROLE=public
BIND=0.0.0.0
PORT=$PUBLIC
BACKEND_PORT=$BACKEND
ENV
cat > /etc/pub-expo/backend.env <<ENV
ROLE=backend
BIND=0.0.0.0
PORT=$BACKEND
ENV
cat > /etc/pub-expo/admin.env <<ENV
ROLE=admin
BIND=0.0.0.0
PORT=$ADMIN
ENV

for role in public backend admin; do
  cat > "/etc/systemd/system/pub-expo-$role.service" <<UNIT
[Unit]
Description=Lab exposition ($role)

[Service]
EnvironmentFile=/etc/pub-expo/$role.env
ExecStart=/usr/bin/python3 /opt/pub-expo/app.py
Restart=on-failure
UNIT
done

systemctl daemon-reload
for role in backend admin public; do
  systemctl start "pub-expo-$role.service"
done

for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PUBLIC/" || true)
  [[ "$code" == 200 ]] && break
  sleep 1
done
[[ "$code" == 200 ]]

cat > /home/student/README-exposition <<TXT
Service publié : le point d'entrée écoute sur le port $PUBLIC de edge.lab.
Le backend de l'application écoute sur le port $BACKEND.
L'administration écoute sur le port $ADMIN.

Réseau de test : le poste client est poste.lab, il n'est pas sur edge.lab.
Seul le point d'entrée doit être joignable depuis le client. Le backend et
l'administration ne doivent être joignables que depuis edge.lab elle-même.
TXT
chown student:student /home/student/README-exposition
