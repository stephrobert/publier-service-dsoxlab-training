#!/usr/bin/env bash
# Pose le banc du lab pub-traefik-dns01 : une autorité ACME de test (Pebble)
# qui valide les défis DNS-01 auprès d'un serveur faisant autorité de test
# (pebble-challtestsrv), et devant lui un fournisseur DNS à comptes limités
# par zone, celui que l'automatisation de l'apprenant doit utiliser.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-traefik-dns01.log) 2>&1
set -x

WORK=/opt/pub-traefik-dns01
ETC=/etc/pub-traefik-dns01
RESEAU=dns01
SOUS_RESEAU=172.30.20.0/24
PASSERELLE=172.30.20.1
IP_AUTORITE_DNS=172.30.20.53

for port in 80 443 14000 15000 8060; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé ; un lab précédent n'a pas été nettoyé." >&2
    exit 1
  fi
done

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0700 -o root -g root "$ETC"

for image in "$IMG_TRAEFIK" "$IMG_WHOAMI" "$IMG_PEBBLE" "$IMG_CHALLTESTSRV"; do
  docker pull "$image"
done

docker network rm "$RESEAU" 2>/dev/null || true
docker network create --driver bridge --subnet "$SOUS_RESEAU" \
  --gateway "$PASSERELLE" "$RESEAU"

docker create --name pub-dns01-config "$IMG_PEBBLE"
docker cp pub-dns01-config:/test/config/pebble-config.json "$WORK/pebble-config.json"
docker cp pub-dns01-config:/test/certs/pebble.minica.pem "$WORK/pebble.minica.pem"
docker rm pub-dns01-config
chmod 0644 "$WORK/pebble-config.json" "$WORK/pebble.minica.pem"

# La plateforme de test. Le serveur faisant autorité n'expose PAS son API de
# gestion sur l'hôte : on ne passe que par le fournisseur, qui porte les
# comptes. `restart` pour que le banc survive à un redémarrage.
cat > "$WORK/platform.yaml" <<YAML
services:
  challtestsrv:
    image: $IMG_CHALLTESTSRV
    container_name: pub-dns01-challtestsrv
    restart: unless-stopped
    command: ["-defaultIPv6", "", "-defaultIPv4", "$PASSERELLE"]
    networks:
      $RESEAU:
        ipv4_address: $IP_AUTORITE_DNS
  pebble:
    image: $IMG_PEBBLE
    container_name: pub-dns01-pebble
    restart: unless-stopped
    command: ["-config", "/test/config/pebble-config.json", "-dnsserver", "$IP_AUTORITE_DNS:8053"]
    environment:
      PEBBLE_VA_NOSLEEP: "1"
    ports:
      - "127.0.0.1:14000:14000"
      - "127.0.0.1:15000:15000"
    volumes:
      - ./pebble-config.json:/test/config/pebble-config.json:ro
    depends_on: [challtestsrv]
    networks:
      $RESEAU:
        aliases: [pebble]
networks:
  $RESEAU:
    external: true
YAML
chown -R student:docker "$WORK"
# L'empreinte de la plateforme posée : un test vérifie que l'autorité n'a pas
# été affaiblie pour accepter un défi sans le contrôler.
sha256sum "$WORK/platform.yaml" "$WORK/pebble-config.json" > /root/.pub-traefik-dns01-plateforme.sha256

# Le fournisseur DNS, en service systemd sur l'hôte. Le compte admin est
# remis à l'apprenant comme le serait la clé maîtresse d'un hébergeur.
install -m 0755 /tmp/pub-traefik-dns01-fournisseur.py "$ETC/fournisseur.py"
MDP_ADMIN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
printf '{"admin": {"mdp": "%s", "zones": ["*"]}}\n' "$MDP_ADMIN" > "$ETC/comptes.json"
chmod 0600 "$ETC/comptes.json"
: > /var/log/pub-traefik-dns01-fournisseur.jsonl
chmod 0600 /var/log/pub-traefik-dns01-fournisseur.jsonl

cat > /etc/systemd/system/pub-traefik-dns01-fournisseur.service <<UNIT
[Unit]
Description=Fournisseur DNS de test du lab pub-traefik-dns01
After=network-online.target docker.service
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 $ETC/fournisseur.py $ETC/comptes.json /var/log/pub-traefik-dns01-fournisseur.jsonl http://$IP_AUTORITE_DNS:8055
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-traefik-dns01-fournisseur.service

cat > /home/student/fournisseur-dns-admin.txt <<TXT
Compte administrateur du fournisseur DNS de test.
Il a TOUTES les zones et peut créer d'autres comptes.

  utilisateur : admin
  mot de passe : $MDP_ADMIN
  API          : http://$PASSERELLE:8060  (depuis le réseau Docker $RESEAU)
                 http://127.0.0.1:8060    (depuis edge.lab)
TXT
chown student:student /home/student/fournisseur-dns-admin.txt
chmod 0600 /home/student/fournisseur-dns-admin.txt

cat > "$WORK/LISEZ-MOI.txt" <<TXT
Répertoire de travail du lab pub-traefik-dns01.

L'autorité Pebble et le serveur DNS faisant autorité de test tournent déjà
via platform.yaml, sur le réseau Docker $RESEAU ($SOUS_RESEAU). Construisez
votre Compose dans compose.yaml.

Le but : servir en HTTPS n'importe quel nom de boutique.lab.test, avec UN
certificat joker *.boutique.lab.test obtenu par le défi ACME DNS-01.

Faits observables :
  - l'annuaire ACME est https://pebble:14000/dir depuis le réseau $RESEAU ;
  - pebble.minica.pem authentifie le serveur HTTPS de Pebble ; ce n'est pas
    la racine des certificats émis ;
  - la racine qui signe les certificats émis se lit sur
    https://localhost:15000/roots/0 ;
  - Pebble lit les enregistrements TXT sur le serveur faisant autorité
    $IP_AUTORITE_DNS, port 8053 ; aucun autre serveur DNS ne connaît
    boutique.lab.test ;
  - ce serveur ne s'administre PAS directement : on passe par le fournisseur
    DNS, une API au protocole « httpreq » de lego (POST /present et
    /cleanup), décrite dans /home/student/fournisseur-dns-admin.txt ;
  - le fournisseur sait créer des comptes limités à une zone :
    POST /comptes {"nom": "...", "zone": "..."}, avec le compte admin ;
  - les ports 80 et 443 sont réservés à Traefik.

Images disponibles, épinglées par digest :
  Traefik : $IMG_TRAEFIK
  whoami  : $IMG_WHOAMI
TXT
chown student:docker "$WORK/LISEZ-MOI.txt"

docker compose -f "$WORK/platform.yaml" up -d
for _ in $(seq 1 30); do
  if curl -skf https://localhost:14000/dir >/dev/null \
     && curl -sf -o /dev/null -w '%{http_code}' -u "admin:$MDP_ADMIN" http://127.0.0.1:8060/comptes | grep -q 200; then
    echo "Pebble et le fournisseur répondent ; le poste est prêt."
    exit 0
  fi
  sleep 1
done
docker compose -f "$WORK/platform.yaml" logs
systemctl status --no-pager pub-traefik-dns01-fournisseur.service || true
echo "Le banc n'a pas répondu à temps." >&2
exit 1
