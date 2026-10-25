#!/usr/bin/env bash
# Pose le producteur et le service de notifications (WebSocket + SSE) du
# lab pub-socle-flux-longs sur edge.lab, ainsi que le client de mesure
# fourni (websockets, asyncio) qui chronomètre chaque flux au lieu de se
# contenter de lire un corps final.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-flux-longs.log) 2>&1
set -x

WORK=/opt/pub-flux
ETC=/etc/pub-flux
STATE=/var/lib/pub-flux

for u in pub-flux-producteur pub-flux-service; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml python3-pip >/dev/null
pip3 install --break-system-packages -q 'websockets==17.3'

install -d -m 0755 "$WORK" "$ETC"
rm -rf "$STATE"
install -d -m 0750 "$STATE"
install -m 0644 /tmp/pub-flux-app.py "$WORK/app.py"
install -m 0755 /tmp/pub-flux-mesure.py "$WORK/mesure_flux.py"

mapfile -t PORTS < <(shuf -i 19900-20199 -n 3)
PRODUCTEUR=${PORTS[0]}
WS=${PORTS[1]}
SSE=${PORTS[2]}

# Politique du service : volontairement incorrecte au départ sur les
# quatre points testés (délai d'écho, taille de tampon SSE, intervalle de
# heartbeat, signalement de panne).
cat > "$ETC/politique.yaml" <<YAML
websocket:
  delai_echo_ms: 3000
sse:
  taille_tampon: 50
inactivite:
  intervalle_heartbeat_s: 9999
panne:
  fermer_proprement: false
YAML
chmod 0644 "$ETC/politique.yaml"

cat > "$ETC/producteur.env" <<ENV
ROLE=producteur
PRODUCTEUR_PORT=$PRODUCTEUR
ENV
cat > "$ETC/service.env" <<ENV
ROLE=service
PRODUCTEUR_PORT=$PRODUCTEUR
WS_PORT=$WS
SSE_PORT=$SSE
POLITIQUE=$ETC/politique.yaml
ENV

for role in producteur service; do
  cat > "/etc/systemd/system/pub-flux-$role.service" <<UNIT
[Unit]
Description=Lab pub-socle-flux-longs ($role)
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
systemctl enable --now pub-flux-producteur.service
sleep 1
systemctl enable --now pub-flux-service.service

cat > "$STATE/etat.json" <<JSON
{
  "producteur_port": $PRODUCTEUR,
  "ws_port": $WS,
  "sse_port": $SSE
}
JSON
chmod 0640 "$STATE/etat.json"
chgrp student "$STATE/etat.json" 2>/dev/null || true

for i in 1 2 3 4 5; do
  if python3 -c "import socket; socket.create_connection(('127.0.0.1', $WS), timeout=1).close()" 2>/dev/null; then
    break
  fi
  sleep 1
done

cat > /home/student/README-flux <<TXT
Lab pub-socle-flux-longs : producteur et service sur edge.lab, 127.0.0.1
uniquement.

- WebSocket (echo) : ws://127.0.0.1:$WS/ws
- SSE              : http://127.0.0.1:$SSE/events
- producteur       : service systemd pub-flux-producteur.service (une
  notification par seconde tant qu'il tourne)

Politique a corriger : $ETC/politique.yaml, relue a chaque message et a
chaque tour de boucle d'un flux : aucun redemarrage necessaire, meme sur
une connexion deja ouverte.

Client de mesure fourni : $WORK/mesure_flux.py
  python3 $WORK/mesure_flux.py websocket <port_ws>
  python3 $WORK/mesure_flux.py sse <port_sse> <duree_s>
  python3 $WORK/mesure_flux.py panne <port_sse> <attente_avant_s> <attente_apres_s>

La derniere commande arrete elle-meme le producteur (sudo systemctl stop
pub-flux-producteur.service) apres l'attente donnee : pensez a le
redemarrer ensuite (sudo systemctl start pub-flux-producteur.service) si
vous l'utilisez a la main.
TXT
chown student:student /home/student/README-flux
