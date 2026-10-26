#!/usr/bin/env bash
# Pose l'etape 1 du plan : la version 1.4.2 publiee en TLS avec SON
# certificat, un flux long disponible, et rien pour livrer.
#
# CE QUE LA FIXTURE NE POSE PAS, A DESSEIN
#   ni `livrer`, ni `revenir`. Ce sont eux le travail. La fixture pose
#   l'etat de depart, les deux builds, les deux certificats, le manifeste
#   et le plan ; le mecanisme de livraison appartient a l'apprenant.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-mise-a-jour.log) 2>&1
set -x

WORK=/opt/pub-nginx-mise-a-jour
PKI="$WORK/pki"
BUILDS="$WORK/builds"
ETAT="$WORK/etat"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl openssl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g student "$ETAT"
install -d -m 0755 -o root -g root "$BUILDS"
install -d -m 0750 -o root -g root "$PKI"

# --------------------------------------------------------------------------
# La PKI : une AC du lab, et UN CERTIFICAT PAR VERSION. Les deux portent le
# meme nom de service, et c'est volontaire : ce qui les distingue est leur
# empreinte, pas leur identite. Le retour arriere doit ramener la version ET
# son certificat, et rien dans le nom ne permet de s'en apercevoir.
# --------------------------------------------------------------------------
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
  -keyout "$PKI/ca.key" -out "$PKI/ca.crt" \
  -subj "/CN=AC interne du lab"

emettre() {
  local version="$1"
  openssl req -newkey rsa:2048 -nodes -sha256 \
    -keyout "$PKI/service-$version.key" -out "$PKI/service-$version.csr" \
    -subj "/CN=service.lab.test/OU=generation $version"
  openssl x509 -req -in "$PKI/service-$version.csr" \
    -CA "$PKI/ca.crt" -CAkey "$PKI/ca.key" -CAcreateserial \
    -out "$PKI/service-$version.crt" -days 825 -sha256 \
    -extfile <(printf 'subjectAltName=DNS:service.lab.test\n')
}

emettre 1.4.2
emettre 1.5.0
chmod 0640 "$PKI"/*.key
chmod 0644 "$PKI"/*.crt "$PKI"/*.csr

empreinte() {
  # `sed 's/.*=//'` et non `'s/.*= //'` : openssl n'ecrit PAS d'espace apres
  # le signe egal. Mesure du 2026-10-26, openssl 3 :
  #   sha256 Fingerprint=87:D7:D1:63:...
  # Avec le motif qui attendait un espace, la ligne sortait entiere, le
  # manifeste portait donc « empreinte_sha256 sha256 Fingerprint=87:... »,
  # soit trois champs la ou le lecteur en attend deux. Il n'y lisait aucune
  # empreinte, et les quatre controles qui comparent au manifeste tombaient
  # en erreur de fixture, avec un message qui accusait le manifeste.
  openssl x509 -in "$PKI/service-$1.crt" -noout -fingerprint -sha256 \
    | sed 's/^.*=//'
}

# --------------------------------------------------------------------------
# Les deux builds. Chacun porte sa version EN DUR dans son propre fichier :
# c'est ce qui permet de mesurer la version REELLEMENT EXECUTEE, par
# opposition a celle qui est installee, ou a celle qu'un lien symbolique
# designe. Un lien bascule sans redemarrage laisse l'ancien code en
# memoire, et le disque ment alors sur ce qui tourne.
# --------------------------------------------------------------------------
poser_build() {
  local version="$1" port="$2"
  install -d -m 0755 "$BUILDS/$version"
  echo "$port" > "$BUILDS/$version/port.txt"
  sed -e "s/@VERSION@/$version/g" -e "s/@PORT@/$port/g" \
    "$WORK/app.modele.py" > "$BUILDS/$version/app.py"
  chmod 0644 "$BUILDS/$version/app.py"
}

cat > "$WORK/app.modele.py" <<'PY'
"""Le service publie. Sa version est en dur : il ne la lit nulle part.

Un service qui lirait sa version dans un fichier dirait ce que le fichier
dit, pas ce qu'il est. Ici, la reponse de /version est la preuve de ce qui
tourne vraiment, et c'est tout l'interet de la mesure.
"""

import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "@VERSION@"
PORT = @PORT@


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, code, corps, entetes=None):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        for cle, valeur in (entetes or {}).items():
            self.send_header(cle, valeur)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        chemin = self.path.split("?", 1)[0].rstrip("/") or "/"
        if chemin == "/version":
            self._rendre(200, ("%s\n" % VERSION).encode())
            return
        if chemin == "/pret":
            self._rendre(200, b"pret\n")
            return
        if chemin == "/flux":
            # Un flux long : une ligne par seconde, pendant deux minutes.
            # C'est ce qu'une bascule mal menee coupe net, et ce qu'un
            # drainage preserve.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for i in range(120):
                    ligne = "data: %s %d\n\n" % (VERSION, i)
                    self.wfile.write(ligne.encode())
                    self.wfile.flush()
                    time.sleep(1)
            except (BrokenPipeError, ConnectionResetError):
                return
            return
        self._rendre(200, ("service %s\n" % VERSION).encode())

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", PORT), Service).serve_forever()
PY

poser_build 1.4.2 18111
poser_build 1.5.0 18112
rm -f "$WORK/app.modele.py"

# --------------------------------------------------------------------------
# Une unite systemd par generation, par instance d'un modele. L'instance
# EST la version : il n'y a donc rien a editer pour livrer, seulement une
# unite a demarrer et une autre a retirer quand elle a fini de servir.
# --------------------------------------------------------------------------
cat > /etc/systemd/system/pub-maj-app@.service <<'UNIT'
[Unit]
Description=Published service, generation %i
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-mise-a-jour/builds/%i/app.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-maj-app@1.4.2.service

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null http://127.0.0.1:18111/pret
  then break; fi
  sleep 1
done

# --------------------------------------------------------------------------
# La publication. Etat de depart : la generation 1.4.2, avec SON certificat.
# --------------------------------------------------------------------------
cat > /etc/nginx/conf.d/service.conf <<'CONF'
upstream generation_active {
    server 127.0.0.1:18111;
}

server {
    listen 80 default_server;
    server_name service.lab.test;
    return 308 https://$host$request_uri;
}

server {
    # `listen ... http2` et non `http2 on;` : la seconde forme n'existe
    # qu'a partir de nginx 1.25.1, et Ubuntu 24.04 livre 1.24.
    listen 443 ssl http2 default_server;
    server_name service.lab.test;

    ssl_certificate     /opt/pub-nginx-mise-a-jour/pki/service-1.4.2.crt;
    ssl_certificate_key /opt/pub-nginx-mise-a-jour/pki/service-1.4.2.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://generation_active;
        proxy_set_header Host $host;
        proxy_read_timeout 10s;
    }

    # Le flux long ne se met ni en tampon ni en borne de lecture courte :
    # une reponse qui dure deux minutes n'est pas une reponse en retard.
    location /flux {
        proxy_pass http://generation_active;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
CONF

nginx -t
systemctl enable --now nginx
systemctl reload nginx

# --------------------------------------------------------------------------
# Le manifeste : ce que chaque generation DOIT etre, et nulle part ailleurs.
# --------------------------------------------------------------------------
cat > "$WORK/manifeste.txt" <<TXT
Manifeste des generations du service.

  Ce fichier est la reference. Une generation est conforme quand les trois
  lignes qui la decrivent sont vraies EN MEME TEMPS : la version servie, le
  port d'ecoute du build, et l'empreinte du certificat publie.

generation 1.4.2
  version_servie   1.4.2
  port             18111
  certificat       $PKI/service-1.4.2.crt
  cle              $PKI/service-1.4.2.key
  empreinte_sha256 $(empreinte 1.4.2)

generation 1.5.0
  version_servie   1.5.0
  port             18112
  certificat       $PKI/service-1.5.0.crt
  cle              $PKI/service-1.5.0.key
  empreinte_sha256 $(empreinte 1.5.0)

  Les deux certificats portent le MEME nom de service, service.lab.test.
  Rien dans le nom ne dit lequel est publie : seule l'empreinte le dit.
  C'est pour cela que le retour arriere doit ramener le certificat
  de la generation, et pas seulement son code.
TXT
chown student:student "$WORK/manifeste.txt"
chmod 0644 "$WORK/manifeste.txt"

cat > "$WORK/plan.txt" <<'TXT'
Le plan de livraison, et ce que la validation en fait.

CE QUE VOUS AVEZ A ECRIRE

  /opt/pub-nginx-mise-a-jour/livrer     executable, prend une version en
                                        argument. Rend la main quand cette
                                        generation est REELLEMENT servie,
                                        avec son certificat. Idempotent.

  /opt/pub-nginx-mise-a-jour/revenir    executable, sans argument. Ramene la
                                        generation precedemment servie, avec
                                        SON certificat.

  Le langage vous appartient : la validation ne fait que les executer. Elle
  les appelle avec sudo, depuis la machine elle-meme.

  `revenir` a besoin de savoir d'ou il vient. Cette memoire doit survivre a
  un redemarrage de la machine : /run et /tmp n'en sont pas.

LA SEQUENCE QUE LA VALIDATION JOUE

  etape 1   l'etat pose : generation 1.4.2.
  etape 2   `livrer 1.5.0`, et la mesure pendant la bascule.
  etape 3   `revenir`, qui doit ramener 1.4.2 et son certificat.
  etape 4   un redemarrage de la machine, sans aucune intervention apres.

  Entre chaque etape, elle compare au manifeste la version SERVIE et
  l'empreinte du certificat PUBLIE. Ni ce que le disque contient, ni ce
  qu'un lien symbolique designe : ce que le service rend, depuis le client.

CE QUE LA BASCULE DOIT TENIR

  trafic court   une sonde continue tourne pendant `livrer`. Au plus UNE
                 requete en echec sur la serie. Les deux generations ont
                 chacune leur port : elles peuvent donc tourner en meme
                 temps, et c'est ce qui rend le zero-erreur atteignable.
                 Arreter avant de demarrer ouvre une fenetre que rien ne
                 referme.

  flux long      un flux ouvert AVANT la bascule doit continuer a recevoir
                 des donnees APRES. Une livraison ne coupe donc pas la
                 generation precedente : c'est la livraison SUIVANTE qui la
                 retire, quand elle n'a plus rien a servir.

  Et il faut l'ECRIRE. /opt/pub-nginx-mise-a-jour/journal.md porte vos
  mesures et ce que vous en concluez : combien d'erreurs, sur le trafic
  court comme sur le flux long, et pourquoi. La validation verifie que ce
  journal existe et parle du flux long ; elle ne juge pas le texte, qui se
  lit.

APRES LE REDEMARRAGE

  La recette doit passer sans qu'on touche a rien. Un service qui repond
  aujourd'hui et ne revient pas demain n'est pas livre, il est lance.
TXT
chown student:student "$WORK/plan.txt"
chmod 0644 "$WORK/plan.txt"

for _ in $(seq 1 30); do
  if curl --max-time 3 --silent --insecure --output /dev/null \
      https://127.0.0.1/version; then
    SERVIE="$(curl --max-time 3 --silent --insecure https://127.0.0.1/version)"
    if [ "$SERVIE" = "1.4.2" ]; then
      echo "Situation posée : la génération 1.4.2 est publiée."
      exit 0
    fi
    echo "La version servie est '$SERVIE' et non 1.4.2." >&2
    exit 1
  fi
  sleep 1
done
echo "Le service ne répond pas en HTTPS." >&2
exit 1
