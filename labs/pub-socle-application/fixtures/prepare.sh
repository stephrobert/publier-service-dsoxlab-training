#!/usr/bin/env bash
# Pose le point d'entrée TLS, l'application et les deux pages d'origine du
# lab pub-socle-application sur edge.lab, ainsi que le navigateur
# automatisable fourni (Playwright + Chromium) qui observe les quatre
# points depuis où ils comptent réellement.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-application.log) 2>&1
set -x

WORK=/opt/pub-app
ETC=/etc/pub-app
STATE=/var/lib/pub-app
CERTS="$ETC/certs"
BROWSERS=/opt/ms-playwright

for u in pub-app-entree pub-app-backend pub-app-partenaire pub-app-intrus; do
  systemctl stop "$u.service" 2>/dev/null || true
done

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-yaml python3-pip openssl >/dev/null

install -d -m 0755 "$WORK" "$ETC" "$CERTS"
rm -rf "$STATE"
install -d -m 0750 "$STATE"
install -m 0644 /tmp/pub-app-app.py "$WORK/app.py"
install -m 0755 /tmp/pub-app-verifier.py "$WORK/verifier_navigateur.py"

# Certificat auto-signé pour le seul maillon qui termine TLS : tout tourne
# en boucle locale, le navigateur automatisable ignore explicitement
# l'erreur de confiance (ce lab porte sur la session, le cookie et les
# origines, pas sur l'identité TLS déjà couverte par pub-socle-tls).
openssl req -x509 -new -nodes -newkey rsa:2048 -days 30 -sha256 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  -keyout "$CERTS/entree.key" -out "$CERTS/entree.crt" 2>/dev/null
chmod 0644 "$CERTS"/*.key "$CERTS"/*.crt

mapfile -t PORTS < <(shuf -i 19600-19899 -n 4)
ENTREE=${PORTS[0]}
BACKEND=${PORTS[1]}
PARTENAIRE=${PORTS[2]}
INTRUS=${PORTS[3]}
SECRET=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
ORIGINE_PARTENAIRE="http://127.0.0.1:$PARTENAIRE"

# Politique de l'application : volontairement incorrecte au départ sur les
# quatre points testés (schéma transmis, portée du cookie, origines CORS,
# confiance à l'en-tête d'identité).
cat > "$ETC/politique.yaml" <<YAML
entete_proto:
  transmettre: false
cookie:
  domaine: "cookie.invalide.pub-app.test"
cors:
  autoriser_toutes_origines: true
  origine_autorisee: "$ORIGINE_PARTENAIRE"
identite:
  faire_confiance_entete_client: true
YAML
chmod 0644 "$ETC/politique.yaml"

cat > "$ETC/backend.env" <<ENV
ROLE=backend
PORT=$BACKEND
SECRET=$SECRET
POLITIQUE=$ETC/politique.yaml
ENV
cat > "$ETC/entree.env" <<ENV
ROLE=entree
PORT=$ENTREE
BACKEND_PORT=$BACKEND
SECRET=$SECRET
POLITIQUE=$ETC/politique.yaml
TLS_CERT=$CERTS/entree.crt
TLS_KEY=$CERTS/entree.key
ENV
cat > "$ETC/partenaire.env" <<ENV
ROLE=origine
PORT=$PARTENAIRE
ORIGINE_NOM=partenaire
ENTREE_PORT=$ENTREE
ENV
cat > "$ETC/intrus.env" <<ENV
ROLE=origine
PORT=$INTRUS
ORIGINE_NOM=intrus
ENTREE_PORT=$ENTREE
ENV

for role in backend entree partenaire intrus; do
  cat > "/etc/systemd/system/pub-app-$role.service" <<UNIT
[Unit]
Description=Lab pub-socle-application ($role)
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
for role in backend entree partenaire intrus; do
  systemctl enable --now "pub-app-$role.service"
done

cat > "$STATE/etat.json" <<JSON
{
  "entree_port": $ENTREE,
  "backend_port": $BACKEND,
  "partenaire_port": $PARTENAIRE,
  "intrus_port": $INTRUS,
  "origine_partenaire": "$ORIGINE_PARTENAIRE",
  "origine_intruse": "http://127.0.0.1:$INTRUS"
}
JSON
chmod 0640 "$STATE/etat.json"
chgrp student "$STATE/etat.json" 2>/dev/null || true

# Navigateur automatisable fourni : installé une fois pour tous les
# usagers, dans un emplacement lisible par tous, pour que les tests comme
# l'apprenant puissent l'exécuter sans droits supplémentaires.
if [ ! -d "$BROWSERS" ] || [ -z "$(ls -A "$BROWSERS" 2>/dev/null)" ]; then
  pip3 install --break-system-packages -q playwright
  PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" python3 -m playwright install --with-deps chromium
  chmod -R a+rX "$BROWSERS"
fi

for i in 1 2 3 4 5; do
  if curl -sk --max-time 2 "https://127.0.0.1:$ENTREE/login" >/dev/null; then
    break
  fi
  sleep 1
done

cat > /home/student/README-app <<TXT
Lab pub-socle-application : application et point d'entree sur edge.lab,
127.0.0.1 uniquement.

- entree (TLS)   : https://127.0.0.1:$ENTREE/
- backend (clair): 127.0.0.1:$BACKEND (jamais joignable depuis l'exterieur)
- page partenaire: http://127.0.0.1:$PARTENAIRE/
- page intruse   : http://127.0.0.1:$INTRUS/

Compte de test : usager=etudiant, motdepasse=motdepasse-correct.

Politique a corriger : $ETC/politique.yaml (relue a chaque requete, aucun
redemarrage necessaire).

Navigateur automatisable fourni : $WORK/verifier_navigateur.py
  PLAYWRIGHT_BROWSERS_PATH=$BROWSERS python3 $WORK/verifier_navigateur.py <verification>
Verifications disponibles : parcours, cors, identite.
TXT
chown student:student /home/student/README-app

