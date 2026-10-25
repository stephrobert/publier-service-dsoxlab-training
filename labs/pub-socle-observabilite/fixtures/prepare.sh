#!/usr/bin/env bash
# Pose la route métier, son générateur de trafic, son exportateur et son
# évaluateur sur edge.lab : la collecte (journal + exportateur) est saine dès
# le départ, mais la politique de l'évaluateur est réglée pour ne jamais
# distinguer correctement panne réelle, absence de trafic et collecte perdue.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-observabilite.log) 2>&1
set -x

WORK=/opt/pub-obs
ETC=/etc/pub-obs
STATE=/var/lib/pub-obs
LOGDIR=/var/log/pub-obs
ACCES_LOG=$LOGDIR/acces.log

for u in pub-obs-metier pub-obs-generateur pub-obs-exportateur pub-obs-evaluateur; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml >/dev/null

install -d -m 0755 "$WORK" "$ETC" "$LOGDIR"
rm -rf "$STATE"
install -d -m 0750 "$STATE"
install -m 0644 /tmp/pub-obs-app.py "$WORK/app.py"
rm -f "$ACCES_LOG"
: > "$ACCES_LOG"
chmod 0644 "$ACCES_LOG"

mapfile -t PORTS < <(shuf -i 19700-19989 -n 3)
PORT_METIER=${PORTS[0]}
PORT_EXPORTATEUR=${PORTS[1]}
PORT_EVALUATEUR=${PORTS[2]}

# Politique volontairement incorrecte sur ses trois réglages : un seuil de
# fraîcheur de collecte bien trop tolérant, un seuil minimal de trafic bien
# trop haut (toujours lu comme une absence), et un seuil d'erreur hors
# d'atteinte (jamais d'alerte).
cat > "$ETC/politique.yaml" <<YAML
collecte:
  staleness_max_s: 600
trafic:
  seuil_minimum: 500
alerte:
  seuil_taux_erreur: 1.1
YAML
chmod 0644 "$ETC/politique.yaml"

for role in metier exportateur evaluateur generateur; do
  cat > "/etc/systemd/system/pub-obs-$role.service" <<UNIT
[Unit]
Description=Lab pub-socle-observabilite ($role)
After=network.target

[Service]
Environment=ROLE=$role
Environment=ACCES_LOG=$ACCES_LOG
Environment=PANNE_FLAG=$STATE/panne
Environment=POLITIQUE=$ETC/politique.yaml
Environment=PORT_METIER=$PORT_METIER
Environment=PORT_EXPORTATEUR=$PORT_EXPORTATEUR
Environment=PORT=$PORT_METIER
Environment=INTERVALLE_S=0.3
ExecStart=/usr/bin/python3 $WORK/app.py
Restart=on-failure
RestartSec=1
User=root

[Install]
WantedBy=multi-user.target
UNIT
done

# Chaque unité porte son propre PORT effectif (exportateur, évaluateur).
sed -i "s/^Environment=PORT=.*/Environment=PORT=$PORT_EXPORTATEUR/" \
  /etc/systemd/system/pub-obs-exportateur.service
sed -i "s/^Environment=PORT=.*/Environment=PORT=$PORT_EVALUATEUR/" \
  /etc/systemd/system/pub-obs-evaluateur.service

systemctl daemon-reload
systemctl enable --now pub-obs-metier.service
for _ in 1 2 3 4 5; do
  python3 -c "import socket; socket.create_connection(('127.0.0.1', $PORT_METIER), timeout=1).close()" \
    2>/dev/null && break
  sleep 1
done
systemctl enable --now pub-obs-exportateur.service
systemctl enable --now pub-obs-evaluateur.service
systemctl enable --now pub-obs-generateur.service

# Laisse le générateur, l'exportateur et l'évaluateur tourner un peu, pour que
# le premier /diagnostic observé ne tombe pas sur un démarrage à froid.
sleep 4

# Jeu de requêtes connu (historique) pour le point "sli" : dix requêtes
# métier (cinq succès, cinq échecs, ratio vrai 0.5) et dix requêtes de santé,
# toutes des succès. Un apprenant qui inclut /sante dans son dénominateur
# obtient 0.75 au lieu de 0.5 : l'écart est le test.
NONCE=$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')
# Horodaté dans le passé : hors de la fenêtre glissante de l'exportateur
# (10 s), pour ne pas fausser la classification au tout premier /diagnostic.
TS_BASE=$(( $(date +%s) - 3600 ))
for i in $(seq 1 5); do
  echo "{\"ts\": $TS_BASE.0, \"id\": \"hist-ok-$NONCE-$i\", \"route\": \"/commande\", \"code\": 200, \"latence_ms\": 25, \"lot\": \"historique\"}" >> "$ACCES_LOG"
done
for i in $(seq 1 5); do
  echo "{\"ts\": $TS_BASE.0, \"id\": \"hist-ko-$NONCE-$i\", \"route\": \"/commande\", \"code\": 500, \"latence_ms\": 80, \"lot\": \"historique\"}" >> "$ACCES_LOG"
done
for i in $(seq 1 10); do
  echo "{\"ts\": $TS_BASE.0, \"id\": \"hist-sante-$NONCE-$i\", \"route\": \"/sante\", \"code\": 200, \"latence_ms\": 5, \"lot\": \"historique\"}" >> "$ACCES_LOG"
done

# Un incident déjà survenu et déjà journalisé, à corréler pour le point
# "correlation" : requête métier en échec, latence pincée pour être
# reproductible à la relecture.
INCIDENT_ID="incident-$NONCE"
curl -s -o /dev/null -H "X-Request-Id: $INCIDENT_ID" -H "X-Force-Code: 500" \
  -H "X-Force-Latency-Ms: 137" "http://127.0.0.1:$PORT_METIER/commande" || true

cat > "$STATE/etat.json" <<JSON
{
  "port_metier": $PORT_METIER,
  "port_exportateur": $PORT_EXPORTATEUR,
  "port_evaluateur": $PORT_EVALUATEUR,
  "incident_id": "$INCIDENT_ID"
}
JSON
chmod 0640 "$STATE/etat.json"
chgrp student "$STATE/etat.json" 2>/dev/null || true

cat > /home/student/README-obs <<TXT
Lab pub-socle-observabilite : route métier, générateur de trafic,
exportateur et évaluateur tournent sur edge.lab, en boucle locale.

- route métier (/commande, /sante) : http://127.0.0.1:$PORT_METIER/
- exportateur (compteurs bruts, fenêtre glissante de 10 s) :
  http://127.0.0.1:$PORT_EXPORTATEUR/metrics
- évaluateur (classification) : http://127.0.0.1:$PORT_EVALUATEUR/diagnostic
- journal des accès : $ACCES_LOG (une ligne JSON par requête : ts, id,
  route, code, latence_ms, lot)
- politique de l'évaluateur, relue en continu, aucun redémarrage requis :
  $ETC/politique.yaml

Incident déjà survenu et déjà journalisé, à corréler : id $INCIDENT_ID.

Simuler une panne applicative réelle : poser le fichier $STATE/panne (la
route /commande répond alors 500). Le retirer répare la route.

La route /sante n'est jamais une route d'affaires : elle ne doit jamais
compter dans votre définition du SLI.
TXT
chown student:student /home/student/README-obs
