#!/usr/bin/env bash
# Pose la situation : une politique de cache et de delais RAPIDE ET
# DANGEREUSE, deja en service.
#
# Elle n'est pas vide, contrairement au lab de la politique d'acces, et c'est
# voulu : la fiche demande de CORRIGER une politique fournie. Elle accelere
# reellement les reponses, et elle melange les utilisateurs, double les
# commandes et ne borne rien.
#
# CE QUE LE SETUP NE FAIT PAS : il ne corrige aucun des quatre defauts.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-cache-delais.log) 2>&1
set -x

WORK=/opt/pub-socle-cache-delais

systemctl stop pub-cache-passerelle.service pub-cache-app.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-cache-passerelle.service \
      /etc/systemd/system/pub-cache-app.service
systemctl daemon-reload
for port in 80 18091; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -o student -g student -m 0644 /tmp/pub-cache-application.py "$WORK/application.py"
install -o root -g root -m 0755 /tmp/pub-cache-passerelle.py "$WORK/passerelle.py"

# Le compteur metier part de zero : la validation compare un avant et un
# apres, et un compteur herite d'un essai precedent fausserait l'ecart.
echo '{"commandes": 0}' > "$WORK/commandes.json"
chmod 0644 "$WORK/commandes.json"

# LA POLITIQUE FOURNIE. Chacune de ses quatre lignes est un defaut.
cat > "$WORK/politique-cache.yaml" <<'YAML'
# Politique de cache et de delais. La passerelle la relit a CHAQUE requete.
#
# Elle a ete ecrite pour aller vite, et elle y arrive. Elle a aussi quatre
# defauts, un par controle de la validation.

cache:
  # Tout est mis en cache, y compris ce qui est prive.
  cacher:
    - /public
    - /prive
  # Et rien ne distingue deux reponses : ni la langue, ni l'identite.
  varier_sur: []

tentatives:
  # On rejoue tout ce qui echoue, « pour la robustesse ».
  rejouer:
    - GET
    - POST

delais:
  # Aucune borne de lecture : on attend le backend aussi longtemps qu'il
  # faut, et l'appelant attend avec nous.
  lecture: 600
YAML
chown student:student "$WORK/politique-cache.yaml"
chmod 0664 "$WORK/politique-cache.yaml"

cat > /home/student/identites-cache.txt <<'TXT'
Identites du banc, a presenter en en-tete :

    Authorization: Bearer <jeton>

  alice   jeton-alice-3b21
  bob     jeton-bob-9d47

Les routes de l'application :

  GET  /public    identique pour tous, mais VARIE selon Accept-Language.
                  Elle porte un numero tire au hasard a chaque passage :
                  deux reponses identiques prouvent un cache.
  GET  /prive     la donnee de l'utilisateur identifie par Authorization.
  POST /commande  incremente le compteur metier PUIS coupe sans repondre.
  GET  /lent      repond au bout de deux secondes.
  GET  /panne     ne repond jamais.

Le compteur metier est dans /opt/pub-socle-cache-delais/commandes.json.
TXT
chown student:student /home/student/identites-cache.txt
chmod 0644 /home/student/identites-cache.txt

cat > /etc/systemd/system/pub-cache-app.service <<'UNIT'
[Unit]
Description=Application metier du lab pub-socle-cache-delais
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-socle-cache-delais/application.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/pub-cache-passerelle.service <<'UNIT'
[Unit]
Description=Passerelle de cache du lab pub-socle-cache-delais
After=network.target pub-cache-app.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-socle-cache-delais/passerelle.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now pub-cache-app.service
systemctl enable --now pub-cache-passerelle.service

for _ in $(seq 1 30); do
  if curl --max-time 3 --silent --output /dev/null http://127.0.0.1/public; then
    echo "Situation posée : une politique rapide, et dangereuse."
    exit 0
  fi
  sleep 1
done
journalctl -u pub-cache-passerelle -u pub-cache-app --no-pager -n 40
echo "La passerelle ou l'application ne répond pas." >&2
exit 1
