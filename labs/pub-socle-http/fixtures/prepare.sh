#!/usr/bin/env bash
# Pose la situation : une API de commandes qui tourne, et le dossier de l'apprenant.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-http.log) 2>&1
set -x

WORK=/opt/pub-http
STATE=/var/lib/pub-api

systemctl stop pub-api.service 2>/dev/null || true
id api >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin api

install -d -m 0755 "$WORK"
install -m 0644 /tmp/pub-socle-api.py "$WORK/api.py"
rm -rf "$STATE"
install -d -m 0750 -o api -g api "$STATE"

# Port et jeton tirés au hasard : une réponse recopiée d'un autre poste ne passe pas.
API_PORT=$(shuf -i 18100-18499 -n 1)
JETON=$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n')

cat > /etc/systemd/system/pub-api.service <<UNIT
[Unit]
Description=API de commandes (lab HTTP)

[Service]
User=api
StateDirectory=pub-api
Environment=API_PORT=$API_PORT
ExecStart=/usr/bin/python3 $WORK/api.py
UNIT

cat > /home/student/README-api <<TXT
API de commandes : http://127.0.0.1:$API_PORT
Jeton de recette : $JETON

POST /commandes                 crée une commande (corps JSON : {"ref": "..."}), répond 201
GET  /commandes/<ref>           200 si la commande existe, 404 sinon
GET  /refus                     refus applicatif
GET  /erreur                    erreur serveur
POST /redir/<code>/commandes    répond <code> avec Location: /commandes
En-tête Idempotency-Key         une même clé ne crée qu'une seule commande
TXT
chown student:student /home/student/README-api

systemctl daemon-reload
systemctl start pub-api.service
for _ in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORT/commandes/inconnue" || true)
  [[ "$code" == 404 ]] && exit 0
  sleep 1
done
echo "l'API n'a pas démarré" >&2
exit 1
