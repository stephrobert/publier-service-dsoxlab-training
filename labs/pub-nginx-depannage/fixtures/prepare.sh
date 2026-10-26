#!/usr/bin/env bash
# Pose une pile SAINE, puis injecte UNE panne tiree au hasard parmi cinq,
# et un bruit de configuration qui ressemble a une cause sans en etre une.
#
# LES CINQ VARIANTES
#   selection   une location en expression reguliere eclipse le prefixe
#               /api/, qui part donc vers le mauvais backend.
#   permission  la racine statique passe en 0700 root:root : 403.
#   dns         la ligne de /etc/hosts qui resout le backend disparait.
#               `nginx -t` echoue, et le service ne redemarre pas.
#   tls         le magasin de confiance du proxy est remplace par une AC
#               etrangere : la route /api/ sort en 502.
#   timeout     proxy_read_timeout tombe a 1s : la route lente sort en 504.
#
# LE BRUIT, LUI, EST TOUJOURS LA, ET N'EST JAMAIS LA CAUSE : un bloc server
# pour un nom de domaine abandonne, un conf.d/ qui ne contient que des
# commentaires, un `gzip on` en double, et un proxy_pass commente qui porte
# un mauvais port. Chacun a l'air suspect. Aucun n'explique la panne.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-depannage.log) 2>&1
set -x

WORK=/opt/pub-nginx-depannage
ETAT="$WORK/etat"
PKI="$WORK/pki"
STATIQUE=/var/www/catalogue

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl openssl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g student "$ETAT"
install -d -m 0750 -o root -g root "$PKI"

# --------------------------------------------------------------------------
# Les marqueurs. Chaque backend rend le sien, tire ici : c'est ce qui rend
# une confusion de route mesurable. Deux backends qui rendraient le meme
# corps ne prouveraient rien.
# --------------------------------------------------------------------------
for quoi in app api statique; do
  # `head` en tete de tube : voir pub-nginx-cache. Une source infinie
  # derriere un `head` final est un SIGPIPE garanti.
  head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$ETAT/nonce-$quoi.txt"
done
chown -R student:student "$ETAT"
chmod 0644 "$ETAT"/nonce-*.txt

# --------------------------------------------------------------------------
# La PKI interne. Une AC de confiance pour le vrai backend, une AC etrangere
# pour l'imposteur, qui porte en plus un SAN qui ne correspond pas.
# --------------------------------------------------------------------------
openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
  -keyout "$PKI/ca.key" -out "$PKI/ca.crt" \
  -subj "/CN=AC interne du lab"

openssl req -newkey rsa:2048 -nodes -sha256 \
  -keyout "$PKI/api.key" -out "$PKI/api.csr" \
  -subj "/CN=api-interne.lab"
openssl x509 -req -in "$PKI/api.csr" -CA "$PKI/ca.crt" -CAkey "$PKI/ca.key" \
  -CAcreateserial -out "$PKI/api.crt" -days 825 -sha256 \
  -extfile <(printf 'subjectAltName=DNS:api-interne.lab\n')

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
  -keyout "$PKI/ac-etrangere.key" -out "$PKI/ac-etrangere.crt" \
  -subj "/CN=AC etrangere"
openssl req -newkey rsa:2048 -nodes -sha256 \
  -keyout "$PKI/imposteur.key" -out "$PKI/imposteur.csr" \
  -subj "/CN=pas-le-bon.lab"
openssl x509 -req -in "$PKI/imposteur.csr" \
  -CA "$PKI/ac-etrangere.crt" -CAkey "$PKI/ac-etrangere.key" \
  -CAcreateserial -out "$PKI/imposteur.crt" -days 825 -sha256 \
  -extfile <(printf 'subjectAltName=DNS:pas-le-bon.lab\n')

chmod 0640 "$PKI"/*.key
chmod 0644 "$PKI"/*.crt
install -m 0644 "$PKI/ca.crt" /etc/nginx/backend-ca.crt

# --------------------------------------------------------------------------
# Les trois backends. Un seul programme, trois roles.
# --------------------------------------------------------------------------
cat > "$WORK/backend.py" <<'PY'
"""Un backend de lab : rend son marqueur, et sait etre lent ou ne jamais finir.

En TLS si un certificat lui est donne, en clair sinon. Il n'ecoute que sur
la boucle locale : un backend joignable depuis l'exterieur est une des
choses que la validation refuse.
"""

import argparse
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARGS = None
MARQUEUR = ""


class Backend(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, code, corps):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        chemin = self.path.split("?", 1)[0].rstrip("/")
        if chemin.endswith("/lent") or chemin == "/lent":
            # Trois secondes : au-dela de la minute d'un defaut Nginx, bien
            # en dessous de la borne que la recette demande.
            time.sleep(3)
            self._rendre(200, ("lent %s %s\n" % (ARGS.role, MARQUEUR)).encode())
            return
        if chemin.endswith("/sans-fin") or chemin == "/sans-fin":
            # N'envoie jamais rien et ne ferme jamais. C'est ce que borne
            # proxy_read_timeout, et ce qu'une borne absente laisse pendre.
            time.sleep(600)
            self._rendre(200, b"jamais\n")
            return
        self._rendre(200, ("%s %s\n" % (ARGS.role, MARQUEUR)).encode())

    def log_message(self, *args):
        return


def main():
    global ARGS, MARQUEUR
    p = argparse.ArgumentParser()
    p.add_argument("--role", required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--marqueur", required=True)
    p.add_argument("--cert")
    p.add_argument("--cle")
    ARGS = p.parse_args()
    with open(ARGS.marqueur, encoding="utf-8") as f:
        MARQUEUR = f.read().strip()

    serveur = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Backend)
    if ARGS.cert:
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexte.load_cert_chain(ARGS.cert, ARGS.cle)
        serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
    serveur.serve_forever()


main()
PY
chmod 0644 "$WORK/backend.py"

poser_unite() {
  local nom="$1" role="$2" port="$3" marqueur="$4" extra="$5"
  cat > "/etc/systemd/system/pub-nginx-depannage-$nom.service" <<UNIT
[Unit]
Description=Backend $role for the Nginx troubleshooting lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-depannage/backend.py \\
  --role $role --port $port \\
  --marqueur /opt/pub-nginx-depannage/etat/nonce-$marqueur.txt $extra
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
}

poser_unite app app 18101 app ""
poser_unite api api 18102 api \
  "--cert $PKI/api.crt --cle $PKI/api.key"
# L'imposteur rend le MARQUEUR DE L'API : s'il etait un jour accepte, sa
# reponse serait indiscernable de celle du vrai backend. C'est exactement ce
# que la sonde de confiance doit interdire, et un corps different aurait
# rendu la sonde facile a passer pour de mauvaises raisons.
poser_unite imposteur imposteur 18103 api \
  "--cert $PKI/imposteur.crt --cle $PKI/imposteur.key"

systemctl daemon-reload
systemctl enable --now pub-nginx-depannage-app.service
systemctl enable --now pub-nginx-depannage-api.service
systemctl enable --now pub-nginx-depannage-imposteur.service

# --------------------------------------------------------------------------
# La racine statique, et la resolution du backend.
# --------------------------------------------------------------------------
install -d -m 0755 -o root -g root "$STATIQUE"
printf 'catalogue statique %s\n' "$(cat "$ETAT/nonce-statique.txt")" \
  > "$STATIQUE/index.html"
chmod 0644 "$STATIQUE/index.html"

sed -i '/dsoxlab-pub-nginx-depannage/d' /etc/hosts
echo "127.0.0.1 api-interne.lab # dsoxlab-pub-nginx-depannage" >> /etc/hosts

# --------------------------------------------------------------------------
# La configuration SAINE. C'est elle que l'injection va abimer.
# --------------------------------------------------------------------------
cat > /etc/nginx/conf.d/publication.conf <<'CONF'
# Du bruit, pas une cause : un nom de domaine abandonne qui ne sert plus.
server {
    listen 80;
    server_name ancien.lab.test;
    return 404;
}

server {
    listen 80 default_server;
    server_name publication.lab.test;

    root /var/www/catalogue;
    index index.html;

    gzip on;
    gzip on;          # du bruit : un doublon sans effet

    location / {
        try_files $uri $uri/ =404;
    }

    location /app/ {
        # du bruit : un proxy_pass commente qui porte un mauvais port
        # proxy_pass http://127.0.0.1:18999/;
        proxy_pass http://127.0.0.1:18101/;
        proxy_set_header Host $host;
        proxy_read_timeout 10s;
    }

    location /api/ {
        proxy_pass https://api-interne.lab:18102/;
        proxy_set_header Host $host;
        proxy_ssl_verify on;
        proxy_ssl_verify_depth 2;
        proxy_ssl_name api-interne.lab;
        proxy_ssl_trusted_certificate /etc/nginx/backend-ca.crt;
        proxy_read_timeout 10s;
    }

    # LA SONDE DE CONFIANCE. Ce backend n'est pas digne de confiance : son
    # certificat vient d'une autre autorite, et son SAN ne correspond pas.
    # Cette route doit repondre 502, et c'est tout ce qu'elle doit faire.
    # Si elle repond 200, la verification TLS a ete desserree.
    location /api-secondaire/ {
        proxy_pass https://127.0.0.1:18103/;
        proxy_set_header Host $host;
        proxy_ssl_verify on;
        proxy_ssl_verify_depth 2;
        proxy_ssl_name api-interne.lab;
        proxy_ssl_trusted_certificate /etc/nginx/backend-ca.crt;
        proxy_read_timeout 10s;
    }
}
CONF
  /etc/nginx/conf.d/publication.conf

# Du bruit : un fichier de conf.d qui ne contient que des commentaires.
cat > /etc/nginx/conf.d/notes-exploitation.conf <<'CONF'
# Notes d'exploitation, laissees par l'equipe precedente.
#
# Penser a revoir les tailles de buffers un jour.
#   proxy_buffers 8 16k;
#   proxy_busy_buffers_size 32k;
#
# Le certificat du backend a ete renouvele en mars. Rien a faire de plus.
CONF

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 3 --silent --output /dev/null http://127.0.0.1/; then
    break
  fi
  sleep 1
done

# --------------------------------------------------------------------------
# La recette, c'est-a-dire ce que l'apprenant doit retablir en entier.
# --------------------------------------------------------------------------
cat > "$WORK/recette.txt" <<'TXT'
La recette de la publication. Elle est la meme avant et apres la panne :
c'est ce qui doit etre vrai pour que le service soit considere en etat.

  /                    rend la page statique du catalogue, avec son
                       marqueur. Servie par Nginx depuis
                       /var/www/catalogue, et non par un backend.

  /app/                rend le marqueur du backend `app`.

  /api/                rend le marqueur du backend `api`. Et ce doit etre
                       le SIEN : les deux marqueurs sont differents, donc
                       une route qui part vers le mauvais backend se voit.

  /api/lent            rend une reponse en trois secondes environ.

  une requete qui      doit etre coupee par le proxy en MOINS DE QUINZE
  n'avance plus        SECONDES, avec un code de passerelle. Une borne
                       absente n'est pas une borne large : la connexion
                       reste ouverte jusqu'a ce que le client abandonne,
                       et le worker avec elle.

  /api-secondaire/     doit repondre 502, et uniquement 502. C'est une
                       SONDE DE CONFIANCE : ce backend presente un
                       certificat signe par une autre autorite, avec un
                       SAN qui ne correspond pas. Son refus est la preuve
                       que la verification TLS du proxy est stricte.

Les identites et les acces, qui font partie de la recette :

  les workers Nginx ne tournent pas sous root ;
  les ports des backends (18101, 18102, 18103) ne sont joignables que
    depuis la machine elle-meme, jamais depuis le reseau ;
  la racine statique n'est pas ouverte en ecriture a tout le monde.

Ce qu'on attend de vous par ecrit, dans
/opt/pub-nginx-depannage/diagnostic.md :

  le COMPOSANT en cause, la CAUSE, et les OBSERVATIONS qui vous y ont
  menes. La validation automatique ne juge pas ce texte : elle verifie
  qu'il existe et qu'il nomme un composant. Le raisonnement, lui, se lit.
TXT
chown student:student "$WORK/recette.txt"
chmod 0644 "$WORK/recette.txt"

# --------------------------------------------------------------------------
# L'INJECTION. Une variante, tiree au hasard, notee hors de portee.
# --------------------------------------------------------------------------
VARIANTE="$(printf 'selection\npermission\ndns\ntls\ntimeout\n' | shuf -n 1)"
echo "$VARIANTE" > /root/.variante-pub-nginx-depannage
chmod 0600 /root/.variante-pub-nginx-depannage

case "$VARIANTE" in
  selection)
    # Une expression reguliere l'emporte sur un prefixe : /api/ part donc
    # vers le backend `app`.
    python3 - <<'PY'
import pathlib
p = pathlib.Path("/etc/nginx/conf.d/publication.conf")
t = p.read_text(encoding="utf-8")
ajout = """
    location ~ ^/api/ {
        proxy_pass http://127.0.0.1:18101;
        proxy_set_header Host $host;
        proxy_read_timeout 10s;
    }
"""
ancre = "    location /api/ {"
p.write_text(t.replace(ancre, ajout.lstrip("\n") + "\n" + ancre, 1),
             encoding="utf-8")
PY
    nginx -t
    systemctl reload nginx
    ;;
  permission)
    chown -R root:root "$STATIQUE"
    chmod 0700 "$STATIQUE"
    ;;
  dns)
    sed -i '/dsoxlab-pub-nginx-depannage/d' /etc/hosts
    # `nginx -t` echoue desormais : le service ne redemarrera pas, et c'est
    # la panne. On l'arrete pour que l'etat pose soit celui d'un service a
    # terre, et non celui d'un processus qui tourne encore sur une
    # configuration qu'il n'a plus sur le disque.
    systemctl stop nginx
    systemctl start nginx || true
    ;;
  tls)
    install -m 0644 "$PKI/ac-etrangere.crt" /etc/nginx/backend-ca.crt
    systemctl reload nginx
    ;;
  timeout)
    python3 - <<'PY'
import pathlib
p = pathlib.Path("/etc/nginx/conf.d/publication.conf")
t = p.read_text(encoding="utf-8")
# La borne de la route /api/ tombe a une seconde : la route lente sort en
# 504, et rien d'autre ne bouge.
debut = t.index("    location /api/ {")
fin = t.index("    # LA SONDE DE CONFIANCE")
bloc = t[debut:fin].replace("proxy_read_timeout 10s;",
                            "proxy_read_timeout 1s;")
p.write_text(t[:debut] + bloc + t[fin:], encoding="utf-8")
PY
    nginx -t
    systemctl reload nginx
    ;;
esac

# --------------------------------------------------------------------------
# Controle de l'etat pose. Il depend de la variante, et c'est normal : une
# panne de resolution met le service a terre, les quatre autres le laissent
# debout avec une route cassee. Ce qui serait anormal, c'est qu'AUCUNE des
# deux situations ne soit vraie : cela voudrait dire que l'injection n'a
# rien fait, et qu'il n'y a donc rien a diagnostiquer.
# --------------------------------------------------------------------------
if [ "$VARIANTE" = "dns" ]; then
  if systemctl is-active --quiet nginx; then
    echo "L'injection dns n'a pas mis Nginx a terre." >&2
    exit 1
  fi
  echo "Situation posée : le service est à terre."
  exit 0
fi

if ! curl --max-time 5 --silent --output /dev/null http://127.0.0.1/app/; then
  echo "La route /app/ ne répond pas : l'injection a cassé plus que prévu." >&2
  exit 1
fi

MARQUEUR_API="$(cat "$ETAT/nonce-api.txt")"
STATUT_RACINE="$(curl --max-time 5 --silent --output /dev/null \
  --write-out '%{http_code}' http://127.0.0.1/)"
CORPS_API="$(curl --max-time 5 --silent http://127.0.0.1/api/ || true)"
STATUT_LENT="$(curl --max-time 20 --silent --output /dev/null \
  --write-out '%{http_code}' http://127.0.0.1/api/lent || true)"

if [ "$STATUT_RACINE" = "200" ] \
  && [ "${CORPS_API#*"$MARQUEUR_API"}" != "$CORPS_API" ] \
  && [ "$STATUT_LENT" = "200" ]; then
  echo "L'injection $VARIANTE n'a rien cassé : il n'y a rien à diagnostiquer." >&2
  exit 1
fi

echo "Situation posée : une panne réelle, et du bruit autour."
