#!/usr/bin/env bash
# Pose la situation : une racine de confiance de test et quatre points d'accès
# TLS sous le même nom, dont un seul prouve réellement son identité face à
# cette racine. Rien ne modifie l'horloge de l'hôte : le certificat expiré est
# fabriqué hors de sa période de validité, pas observé après avance de date.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-tls.log) 2>&1
set -x

NOM=svc.tls.test
WORK=/etc/pub-tls
CERTS="$WORK/certs"

for u in pub-tls-positif pub-tls-nom pub-tls-chaine pub-tls-date; do
  systemctl stop "$u.service" 2>/dev/null || true
done

install -d -m 0755 "$WORK" "$CERTS" /opt/pub-tls
install -m 0644 /tmp/pub-socle-tls-app.py /opt/pub-tls/app.py
find "$CERTS" -mindepth 1 -delete

# Racine de confiance de test, remise à l'apprenant : c'est le SEUL magasin
# qu'il doit utiliser pour juger les quatre points d'accès.
openssl genrsa -out "$CERTS/root.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/root.key" -sha256 -days 60 \
  -subj "/CN=Racine de test pub-socle-tls" -out "$CERTS/root.pem"

# Intermediaire de la racine : le point d'accès « positif » doit servir
# leaf + intermediaire pour que la chaine se reconstruise jusqu'a la racine.
openssl genrsa -out "$CERTS/inter.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/inter.key" -subj "/CN=Intermediaire de test pub-socle-tls" \
  -out "$CERTS/inter.csr"
printf 'basicConstraints=critical,CA:true\nkeyUsage=critical,keyCertSign,cRLSign\n' \
  > "$CERTS/inter.ext"
openssl x509 -req -in "$CERTS/inter.csr" -CA "$CERTS/root.pem" -CAkey "$CERTS/root.key" \
  -CAcreateserial -days 60 -sha256 -extfile "$CERTS/inter.ext" -out "$CERTS/inter.pem"

# Autorite etrangere : signe un certificat par ailleurs correct, mais que la
# racine remise a l'apprenant ne connait pas.
openssl genrsa -out "$CERTS/rogue.key" 2048 2>/dev/null
openssl req -x509 -new -nodes -key "$CERTS/rogue.key" -sha256 -days 60 \
  -subj "/CN=Autorite etrangere pub-socle-tls" -out "$CERTS/rogue.pem"

# positif : nom correct, signe par l'intermediaire, chaine complete servie.
openssl genrsa -out "$CERTS/positif.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/positif.key" -subj "/CN=$NOM" -out "$CERTS/positif.csr"
printf 'subjectAltName=DNS:%s\n' "$NOM" > "$CERTS/positif.ext"
openssl x509 -req -in "$CERTS/positif.csr" -CA "$CERTS/inter.pem" -CAkey "$CERTS/inter.key" \
  -CAcreateserial -days 30 -sha256 -extfile "$CERTS/positif.ext" -out "$CERTS/positif.crt"
cat "$CERTS/positif.crt" "$CERTS/inter.pem" > "$CERTS/positif-chain.pem"

# nom : seul le nom du certificat change ; meme intermediaire, meme chaine.
openssl genrsa -out "$CERTS/nom.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/nom.key" -subj "/CN=autre.tls.test" -out "$CERTS/nom.csr"
printf 'subjectAltName=DNS:autre.tls.test\n' > "$CERTS/nom.ext"
openssl x509 -req -in "$CERTS/nom.csr" -CA "$CERTS/inter.pem" -CAkey "$CERTS/inter.key" \
  -CAcreateserial -days 30 -sha256 -extfile "$CERTS/nom.ext" -out "$CERTS/nom.crt"
cat "$CERTS/nom.crt" "$CERTS/inter.pem" > "$CERTS/nom-chain.pem"

# chaine : bon nom, mais signe par l'autorite etrangere : la racine remise a
# l'apprenant ne peut pas remonter jusqu'a elle.
openssl genrsa -out "$CERTS/chaine.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/chaine.key" -subj "/CN=$NOM" -out "$CERTS/chaine.csr"
printf 'subjectAltName=DNS:%s\n' "$NOM" > "$CERTS/chaine.ext"
openssl x509 -req -in "$CERTS/chaine.csr" -CA "$CERTS/rogue.pem" -CAkey "$CERTS/rogue.key" \
  -CAcreateserial -days 30 -sha256 -extfile "$CERTS/chaine.ext" -out "$CERTS/chaine.crt"

# date : bon nom, bon intermediaire, mais periode de validite deja ecoulee a
# la fabrication (notAfter avant notBefore) : aucune horloge n'est touchee.
openssl genrsa -out "$CERTS/date.key" 2048 2>/dev/null
openssl req -new -key "$CERTS/date.key" -subj "/CN=$NOM" -out "$CERTS/date.csr"
printf 'subjectAltName=DNS:%s\n' "$NOM" > "$CERTS/date.ext"
# Un certificat REELLEMENT perime, par des dates explicites.
#
# `-days -1` marchait sur l'OpenSSL d'Ubuntu 24.04 et echoue sur celui de
# Debian 13 : « Error: end date before start date ». OpenSSL 3.5 refuse une
# duree negative, et c'est defendable, une duree ne se compte pas a
# l'envers.
#
# `-not_before` et `-not_after` disent la meme chose sans ruse : le
# certificat a ete valide trente jours, et il a expire hier.
DEBUT_PERIME="$(date -u -d '-30 days' +%Y%m%d%H%M%SZ)"
FIN_PERIME="$(date -u -d '-1 day' +%Y%m%d%H%M%SZ)"
openssl x509 -req -in "$CERTS/date.csr" -CA "$CERTS/inter.pem" -CAkey "$CERTS/inter.key" \
  -CAcreateserial -not_before "$DEBUT_PERIME" -not_after "$FIN_PERIME" \
  -sha256 -extfile "$CERTS/date.ext" -out "$CERTS/date.crt"
cat "$CERTS/date.crt" "$CERTS/inter.pem" > "$CERTS/date-chain.pem"

chmod 0644 "$CERTS"/*.pem "$CERTS"/*.crt "$CERTS"/*.key

# Ports tires au hasard : une fiche recopiee d'un autre poste ne passe pas.
mapfile -t PORTS < <(shuf -i 19300-19599 -n 4)
PORT_POSITIF=${PORTS[0]}
PORT_NOM=${PORTS[1]}
PORT_CHAINE=${PORTS[2]}
PORT_DATE=${PORTS[3]}

declare -A UNITE_PORT=(
  [positif]=$PORT_POSITIF
  [nom]=$PORT_NOM
  [chaine]=$PORT_CHAINE
  [date]=$PORT_DATE
)
declare -A UNITE_CERT=(
  [positif]="$CERTS/positif-chain.pem"
  [nom]="$CERTS/nom-chain.pem"
  [chaine]="$CERTS/chaine.crt"
  [date]="$CERTS/date-chain.pem"
)
declare -A UNITE_CLE=(
  [positif]="$CERTS/positif.key"
  [nom]="$CERTS/nom.key"
  [chaine]="$CERTS/chaine.key"
  [date]="$CERTS/date.key"
)

for role in positif nom chaine date; do
  cat > "/etc/systemd/system/pub-tls-$role.service" <<UNIT
[Unit]
Description=Point d'acces TLS ($role) du lab pub-socle-tls

[Service]
ExecStart=/usr/bin/python3 /opt/pub-tls/app.py $role ${UNITE_PORT[$role]} ${UNITE_CERT[$role]} ${UNITE_CLE[$role]}
Restart=on-failure
UNIT
done

systemctl daemon-reload
for role in positif nom chaine date; do
  systemctl start "pub-tls-$role.service"
done

for role in positif nom chaine date; do
  port=${UNITE_PORT[$role]}
  for _ in $(seq 1 20); do
    code=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:$port/" || true)
    [[ "$code" == 200 ]] && break
    sleep 1
  done
  [[ "$code" == 200 ]]
done

cat > "$WORK/etat.json" <<JSON
{
  "nom": "$NOM",
  "ports": {
    "positif": $PORT_POSITIF,
    "nom": $PORT_NOM,
    "chaine": $PORT_CHAINE,
    "date": $PORT_DATE
  },
  "ca": "/home/student/ca.pem"
}
JSON

install -m 0644 "$CERTS/root.pem" /home/student/ca.pem
chown student:student /home/student/ca.pem

cat > /home/student/README-tls <<TXT
Quatre points d'acces TLS tournent sur edge.lab, tous sous le nom $NOM :

  positif : port $PORT_POSITIF
  nom     : port $PORT_NOM
  chaine  : port $PORT_CHAINE
  date    : port $PORT_DATE

Racine de confiance de test, et SEUL magasin a utiliser : /home/student/ca.pem

Verifiez chacun en connectant avec ce magasin, le nom $NOM et sans jamais
ignorer la verification (pas de -k, pas de --insecure). Exemple :

  openssl s_client -connect 127.0.0.1:$PORT_POSITIF -servername $NOM \\
    -verify_hostname $NOM -CAfile /home/student/ca.pem

Ne modifiez pas l'horloge de la machine : le cas « date » est deja hors de sa
periode de validite, sans avance de date necessaire.
TXT
chown student:student /home/student/README-tls
