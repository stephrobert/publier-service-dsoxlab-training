#!/usr/bin/env bash
# Pose le répartiteur et les deux backends du lab pub-socle-disponibilite
# sur edge.lab : un répartiteur opaque qui sonde les deux backends selon
# une politique volontairement trop lente et trop tolérante au départ, et
# qui ne les alterne jamais vraiment tant qu'ils répondent tous les deux.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-disponibilite.log) 2>&1
set -x

WORK=/opt/pub-disp
ETC=/etc/pub-disp
STATE=/var/lib/pub-disp

for u in pub-disp-repartiteur pub-disp-backend-a pub-disp-backend-b; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml >/dev/null

install -d -m 0755 "$WORK" "$ETC"
rm -rf "$STATE"
install -d -m 0750 "$STATE"
install -m 0644 /tmp/pub-disp-app.py "$WORK/app.py"
install -m 0755 /tmp/pub-disp-sonder.py "$WORK/sonder.py"

mapfile -t PORTS < <(shuf -i 19300-19599 -n 3)
REPARTITEUR=${PORTS[0]}
BACKEND_A=${PORTS[1]}
BACKEND_B=${PORTS[2]}

# Politique volontairement incorrecte au départ sur les trois points
# configurables : pas de réelle alternance, sonde trop lente, seuils de
# retrait et de retour bien trop tolérants.
cat > "$ETC/politique.yaml" <<YAML
repartition:
  actif: false
probe:
  intervalle_s: 20
  echecs_avant_retrait: 20
  succes_avant_retour: 20
YAML
chmod 0644 "$ETC/politique.yaml"

cat > "$ETC/backend-a.env" <<ENV
ROLE=backend
PORT=$BACKEND_A
BACKEND_ID=a
DRAPEAU_MALSAIN=$STATE/malsain-a
ENV
cat > "$ETC/backend-b.env" <<ENV
ROLE=backend
PORT=$BACKEND_B
BACKEND_ID=b
DRAPEAU_MALSAIN=$STATE/malsain-b
ENV
cat > "$ETC/repartiteur.env" <<ENV
ROLE=repartiteur
PORT=$REPARTITEUR
PORT_A=$BACKEND_A
PORT_B=$BACKEND_B
POLITIQUE=$ETC/politique.yaml
ENV

for role in backend-a backend-b repartiteur; do
  cat > "/etc/systemd/system/pub-disp-$role.service" <<UNIT
[Unit]
Description=Lab pub-socle-disponibilite ($role)
After=network.target

[Service]
EnvironmentFile=$ETC/$role.env
ExecStart=/usr/bin/python3 $WORK/app.py
Restart=on-failure
RestartSec=1
User=root

[Install]
WantedBy=multi-user.target
UNIT
done

systemctl daemon-reload
systemctl enable --now pub-disp-backend-a.service
systemctl enable --now pub-disp-backend-b.service
sleep 1
systemctl enable --now pub-disp-repartiteur.service

for i in 1 2 3 4 5; do
  if python3 -c "import socket; socket.create_connection(('127.0.0.1', $REPARTITEUR), timeout=1).close()" 2>/dev/null; then
    break
  fi
  sleep 1
done

cat > "$STATE/etat.json" <<JSON
{
  "repartiteur_port": $REPARTITEUR,
  "port_a": $BACKEND_A,
  "port_b": $BACKEND_B
}
JSON
chmod 0640 "$STATE/etat.json"
chgrp student "$STATE/etat.json" 2>/dev/null || true

cat > /home/student/README-disp <<TXT
Lab pub-socle-disponibilite : répartiteur et deux backends sur edge.lab,
127.0.0.1 uniquement.

- répartiteur : http://127.0.0.1:$REPARTITEUR/echo (seul point joignable
  du client)
- backend a   : http://127.0.0.1:$BACKEND_A/echo (jamais censé être
  joint directement en usage normal)
- backend b   : http://127.0.0.1:$BACKEND_B/echo

Politique a corriger : $ETC/politique.yaml (relue a chaque sonde et a
chaque requete, aucun redemarrage necessaire).

Simuler une panne applicative d'un backend : poser le fichier
$STATE/malsain-<a|b> (le backend repond alors 503 sur /sante). Le
retirer restaure la sante.

Sondeur fourni : $WORK/sonder.py
  python3 $WORK/sonder.py echantillon <port_repartiteur> <n>
  python3 $WORK/sonder.py direct <port_backend>
  python3 $WORK/sonder.py indisponible <port>
TXT
chown student:student /home/student/README-disp
