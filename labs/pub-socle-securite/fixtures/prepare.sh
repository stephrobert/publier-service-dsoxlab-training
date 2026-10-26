#!/usr/bin/env bash
# Pose la situation : l'application est publiee, et rien ne la protege.
#
# CE QUE LE SETUP DONNE
#   - l'application metier, sur trois routes, qui ne se protege pas ;
#   - le garde parametrable, qui applique `politique.yaml` a la lettre ;
#   - une politique VIDE, qui laisse donc tout passer ;
#   - l'acces direct a l'application OUVERT sur le reseau du lab ;
#   - les identites de test, dans /home/student/identites.txt.
#
# CE QUE LE SETUP NE FAIT PAS, ET C'EST TOUT LE LAB : il n'ecrit aucune
# regle, ne declare aucun proxy de confiance, n'efface aucun en-tete du
# journal, et ne ferme pas l'acces direct.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-securite.log) 2>&1
set -x

WORK=/opt/pub-socle-securite

systemctl stop pub-securite-garde.service pub-securite-app.service 2>/dev/null || true
rm -f /etc/systemd/system/pub-securite-garde.service \
      /etc/systemd/system/pub-securite-app.service
systemctl daemon-reload
for port in 80 18090; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

# Une regle de filtrage laissee par un essai precedent ferait croire a une
# politique qui tient alors que rien n'a ete ecrit.
while iptables -D INPUT -p tcp --dport 18090 -j REJECT 2>/dev/null; do :; done
while iptables -D INPUT -p tcp --dport 18090 -j DROP 2>/dev/null; do :; done

install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -o student -g student -m 0644 /tmp/pub-securite-application.py "$WORK/application.py"
install -o root -g root -m 0755 /tmp/pub-securite-garde.py "$WORK/garde.py"

# La politique de depart est VIDE, et le dit. Le garde l'applique
# fidelement : tout passe.
cat > "$WORK/politique.yaml" <<'YAML'
# Politique d'acces du service. Le garde la relit a CHAQUE requete.
#
# Tant qu'elle est vide, tout est autorise, tout en-tete d'identite est cru,
# et le journal conserve tout ce qu'il recoit.
#
# Trois cles sont comprises :
#
#   routes:                 un prefixe, et l'identite exigee dessus
#     /admin: admin
#
#   proxys_de_confiance:    les adresses dont un X-Identite est cru
#     - 127.0.0.1
#
#   journal:
#     effacer:              les en-tetes remplaces par [efface] avant ecriture
#       - authorization
YAML
chown student:student "$WORK/politique.yaml"
chmod 0664 "$WORK/politique.yaml"

: > "$WORK/acces.log"
echo '{}' > "$WORK/dossier.json"
chmod 0644 "$WORK/acces.log" "$WORK/dossier.json"

cat > /home/student/identites.txt <<'TXT'
Identites du banc. Le jeton se presente en en-tete :

    Authorization: Bearer <jeton>

  utilisateur   jeton-utilisateur-7f3a
  admin         jeton-admin-91c4
  anonyme       (aucun en-tete)

Le garde accepte aussi un en-tete X-Identite, MAIS seulement si l'appelant
figure dans `proxys_de_confiance`. C'est ce qui distingue un en-tete pose par
un proxy de confiance d'un en-tete forge par n'importe qui.
TXT
chown student:student /home/student/identites.txt
chmod 0644 /home/student/identites.txt

cat > /etc/systemd/system/pub-securite-app.service <<'UNIT'
[Unit]
Description=Application metier du lab pub-socle-securite
After=network.target

[Service]
Type=simple
# L'adresse d'ecoute est parametrable : la refermer sur la boucle locale est
# l'un des deux gestes qui ferment l'acces direct.
Environment=ADRESSE=0.0.0.0
Environment=PORT=18090
ExecStart=/usr/bin/python3 /opt/pub-socle-securite/application.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/pub-securite-garde.service <<'UNIT'
[Unit]
Description=Garde parametrable du lab pub-socle-securite
After=network.target pub-securite-app.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-socle-securite/garde.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now pub-securite-app.service
systemctl enable --now pub-securite-garde.service

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null http://127.0.0.1/ \
     && curl --max-time 2 --silent --output /dev/null http://127.0.0.1:18090/; then
    echo "Situation posée : trois routes publiées, aucune politique."
    exit 0
  fi
  sleep 1
done
journalctl -u pub-securite-garde -u pub-securite-app --no-pager -n 40
echo "Le garde ou l'application ne répond pas." >&2
exit 1
