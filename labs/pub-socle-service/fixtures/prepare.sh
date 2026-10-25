#!/usr/bin/env bash
# Pose la situation : application lancée, dépendance de stock arrêtée.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-service.log) 2>&1
set -x

WORK=/opt/pub-socle
STATE=/var/lib/pub-catalogue

systemctl stop pub-catalogue.service pub-stock.service 2>/dev/null || true
id catalogue >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin catalogue
id stock >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin stock

install -d -m 0755 "$WORK"
install -m 0644 /tmp/pub-socle-app.py "$WORK/app.py"
install -m 0644 /tmp/pub-socle-stock.py "$WORK/stock.py"
rm -rf "$STATE"
install -d -m 0750 -o catalogue -g catalogue "$STATE"

# Ports et titres tirés au hasard : une réponse recopiée d'un autre poste ne passe pas.
APP_PORT=$(shuf -i 18100-18499 -n 1)
STOCK_PORT=$(shuf -i 18500-18899 -n 1)
SUFFIXE=$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')
printf '["Atlas-%s", "Boussole-%s", "Cadran-%s"]\n' "$SUFFIXE" "$SUFFIXE" "$SUFFIXE" > "$WORK/livres.json"
chmod 0644 "$WORK/livres.json"

cat > /etc/systemd/system/pub-stock.service <<UNIT
[Unit]
Description=Service de stock du catalogue (dependance)

[Service]
User=stock
Environment=STOCK_PORT=$STOCK_PORT
Environment=LIVRES_FICHIER=$WORK/livres.json
ExecStart=/usr/bin/python3 $WORK/stock.py
UNIT

cat > /etc/systemd/system/pub-catalogue.service <<UNIT
[Unit]
Description=Application de catalogue

[Service]
User=catalogue
StateDirectory=pub-catalogue
Environment=APP_PORT=$APP_PORT
Environment=STOCK_PORT=$STOCK_PORT
Environment=APP_TITRE=Catalogue-$SUFFIXE
ExecStart=/usr/bin/python3 $WORK/app.py
UNIT

systemctl daemon-reload
systemctl start pub-catalogue.service
for _ in $(seq 1 20); do
  curl -fsS "http://127.0.0.1:$APP_PORT/health" >/dev/null && exit 0
  sleep 1
done
echo "l'application n'a pas démarré" >&2
exit 1
