#!/usr/bin/env bash
# Pose la situation : un catalogue mis en cache, et mal.
#
# LES QUATRE DEFAUTS POSES
#   1. `proxy_ignore_headers Cache-Control Expires Set-Cookie` : le contrat
#      que l'origine annonce sur chacune de ses reponses est jete. C'est LE
#      defaut de fond : il fait mettre en cache le prive, et il fait servir
#      le volatil pendant dix minutes.
#   2. `proxy_cache_key "$uri"` : la cle ne voit ni la langue demandee, ni la
#      session, ni la chaine de requete. Deux reponses differentes se
#      rangent donc au meme endroit, et la premiere arrivee gagne.
#   3. `proxy_cache_valid 200 10m` applique a tout, sans distinction entre
#      une page d'accueil stable et un etat de stock qui bouge.
#   4. `add_header X-Cache-Status "HIT" always` : un entete qui annonce HIT
#      sur TOUTES les reponses, y compris celles qui sortent de l'origine.
#      Il ne mesure rien. Il est la pour montrer ce qu'un entete vaut quand
#      c'est celui qu'on verifie qui l'ecrit.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-cache.log) 2>&1
set -x

WORK=/opt/pub-nginx-cache
ETAT="$WORK/etat"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g student "$ETAT"

# Les deux comptes recoivent un marqueur aleatoire, tire ICI et nulle part
# ailleurs : c'est ce qui rend une fuite d'un compte vers l'autre
# indiscutable. Un corps fixe ne prouverait rien, puisqu'il serait le meme
# des deux cotes.
# `head` EN TETE de tube, et non a sa fin : lire /dev/urandom par `tr`
# jusqu'a ce que `head` ferme le tube tue `tr` par SIGPIPE, et
# `set -o pipefail` fait echouer le script. La source etant infinie, cet
# echec est certain, pas occasionnel.
head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$ETAT/nonce-alpha.txt"
head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$ETAT/nonce-beta.txt"
chown -R student:student "$ETAT"
chmod 0644 "$ETAT"/nonce-*.txt

cat > "$WORK/app.py" <<'PY'
"""L'origine du catalogue. Elle compte ses GENERATIONS DE CORPS.

Pourquoi un compteur, et pourquoi dans l'application : parce qu'un HIT de
cache n'est pas une declaration, c'est un fait. La reponse a ete rendue
sans que l'origine ait rien produit. L'application est le seul endroit
d'ou cela se mesure, et c'est le seul endroit ou Nginx n'a aucune prise.

Un 304 ne compte pas : revalider une entree encore bonne n'est pas la
regenerer, et une politique de validation doit pouvoir passer la mesure.
"""

import hashlib
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ETAT = "/opt/pub-nginx-cache/etat"
VERROU = threading.Lock()
GENERATIONS = {"accueil": 0, "stock": 0, "fiche": 0, "prive": 0}

# L'etat de stock bouge : c'est ce qui permet de mesurer la fraicheur.
STOCK = {"valeur": "stock-initial"}


def _lire(nom):
    with open(os.path.join(ETAT, nom), encoding="utf-8") as f:
        return f.read().strip()


def _compter(ressource):
    with VERROU:
        GENERATIONS[ressource] += 1


class App(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rendre(self, code, corps, entetes):
        self.send_response(code)
        for cle, valeur in entetes.items():
            self.send_header(cle, valeur)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _rendre_304(self, etiquette, entetes):
        self.send_response(304)
        self.send_header("ETag", etiquette)
        for cle, valeur in entetes.items():
            self.send_header(cle, valeur)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _public(self, ressource, corps, cache_control, vary=None):
        """Une ressource publique, avec son ETag et sa revalidation."""
        etiquette = '"%s"' % hashlib.sha256(corps).hexdigest()[:16]
        entetes = {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": cache_control,
            "ETag": etiquette,
        }
        if vary:
            entetes["Vary"] = vary
        if self.headers.get("If-None-Match") == etiquette:
            self._rendre_304(etiquette, {"Cache-Control": cache_control})
            return
        _compter(ressource)
        self._rendre(200, corps, entetes)

    def do_GET(self):
        chemin = self.path.split("?", 1)[0].rstrip("/")
        morceaux = [m for m in chemin.split("/") if m]

        if morceaux[:1] == ["compteur"]:
            with VERROU:
                corps = (
                    " ".join("%s=%d" % kv for kv in sorted(GENERATIONS.items()))
                    + "\n"
                ).encode()
            self._rendre(200, corps, {
                "Content-Type": "text/plain; charset=utf-8",
                "Cache-Control": "no-store",
            })
            return

        # Un jeton de parcours est admis apres le nom de la ressource, et
        # ignore. Il sert a la validation : chaque mesure part ainsi d'une
        # entree de cache FROIDE, quelle que soit la cle choisie par
        # l'apprenant. Sans lui, une mesure heriterait du cache de la
        # precedente et conclurait de travers.
        if morceaux[:1] == ["catalogue"] and len(morceaux) >= 2:
            quoi = morceaux[1]
            if quoi == "accueil":
                self._public(
                    "accueil",
                    b"accueil du catalogue : stable, et public\n",
                    "public, max-age=600",
                )
                return
            if quoi == "stock":
                self._public(
                    "stock",
                    ("etat du stock : %s\n" % STOCK["valeur"]).encode(),
                    "public, max-age=5",
                )
                return
            if quoi == "fiche":
                langue = self.headers.get("Accept-Language", "")
                if "fr" in langue.lower():
                    corps = b"fiche produit : redaction en francais\n"
                else:
                    corps = b"product sheet: written in english\n"
                self._public(
                    "fiche", corps, "public, max-age=600",
                    vary="Accept-Language",
                )
                return

        if morceaux[:2] == ["compte", "prive"]:
            session = ""
            for part in (self.headers.get("Cookie") or "").split(";"):
                if part.strip().startswith("session="):
                    session = part.strip()[len("session="):]
            if session not in ("alpha", "beta"):
                corps = b"il faut une session\n"
                self._rendre(401, corps, {
                    "Content-Type": "text/plain; charset=utf-8",
                    "Cache-Control": "private, no-store",
                })
                return
            _compter("prive")
            nonce = _lire("nonce-%s.txt" % session)
            corps = ("compte %s, marqueur %s\n" % (session, nonce)).encode()
            self._rendre(200, corps, {
                "Content-Type": "text/plain; charset=utf-8",
                "Cache-Control": "private, no-store",
                "Set-Cookie": "vu=1; Path=/",
            })
            return

        corps = b"rien ici\n"
        self._rendre(404, corps, {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": "no-store",
        })

    def do_POST(self):
        """Fait bouger l'etat de stock. Boucle locale seulement."""
        if self.path.split("?", 1)[0].rstrip("/") == "/muter":
            if self.client_address[0] != "127.0.0.1":
                self._rendre(403, b"depuis la boucle locale seulement\n", {
                    "Content-Type": "text/plain; charset=utf-8",
                })
                return
            with VERROU:
                nouveau = os.urandom(6).hex()
                STOCK["valeur"] = nouveau
            self._rendre(200, ("stock=%s\n" % nouveau).encode(), {
                "Content-Type": "text/plain; charset=utf-8",
                "Cache-Control": "no-store",
            })
            return
        self._rendre(404, b"rien ici\n", {
            "Content-Type": "text/plain; charset=utf-8",
        })

    def log_message(self, *args):
        return


ThreadingHTTPServer(("127.0.0.1", 18099), App).serve_forever()
PY
chmod 0644 "$WORK/app.py"

cat > /etc/systemd/system/pub-nginx-cache-app.service <<'UNIT'
[Unit]
Description=Catalogue origin for the Nginx caching lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-cache/app.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-cache-app.service

install -d -m 0700 -o www-data -g www-data /var/cache/nginx/catalogue

cat > /etc/nginx/conf.d/cache.conf <<'CONF'
proxy_cache_path /var/cache/nginx/catalogue
    levels=1:2
    keys_zone=catalogue:10m
    max_size=100m
    inactive=60m;

server {
    listen 80 default_server;
    server_name catalogue.lab.test;

    location / {
        proxy_cache catalogue;

        # La cle ne voit ni la langue demandee, ni la session, ni la chaine
        # de requete : deux reponses differentes se rangent au meme endroit.
        proxy_cache_key "$uri";

        # Tout est garde dix minutes, sans distinguer une page stable d'un
        # etat qui bouge.
        proxy_cache_valid 200 10m;

        # LE DEFAUT DE FOND : le contrat que l'origine annonce sur chacune
        # de ses reponses est jete. Le prive se met donc en cache, et le
        # volatil s'y attarde.
        proxy_ignore_headers Cache-Control Expires Set-Cookie X-Accel-Expires;

        # Un entete qui annonce HIT sur toutes les reponses, y compris
        # celles qui sortent de l'origine. Il ne mesure rien.
        add_header X-Cache-Status "HIT" always;

        proxy_pass http://127.0.0.1:18099;
        proxy_set_header Host $host;
    }
}
CONF
  /etc/nginx/conf.d/cache.conf

cat > "$WORK/contrat-de-contenu.txt" <<'TXT'
Le contrat de contenu du catalogue.

  C'est l'origine qui connait ses reponses, et elle le dit : chacune porte
  un Cache-Control, un ETag, et un Vary quand sa representation varie. Le
  role du cache est d'APPLIQUER ce contrat, pas de le remplacer par une
  duree uniforme.

  /catalogue/accueil   public et stable.
                       Eligible au cache. Une deuxieme demande ne doit rien
                       faire produire a l'origine.

  /catalogue/fiche     public, mais sa REPRESENTATION varie selon la langue
                       demandee (Accept-Language). L'origine annonce
                       Vary: Accept-Language. Une demande en anglais ne doit
                       jamais recevoir la redaction francaise, ni l'inverse.

  /catalogue/stock     public, mais il bouge.
                       Ne jamais servir un etat vieux de plus de cinq
                       secondes. Il reste neanmoins eligible au cache ou a
                       la validation : deux demandes qui se suivent ne
                       doivent pas faire produire deux corps.

  /compte/prive        authentifie par un cookie de session, et PRIVE.
                       L'origine annonce Cache-Control: private, no-store.
                       Aucune reponse d'un compte ne doit jamais etre rendue
                       a un autre compte, meme cache chaud.

  Un jeton de parcours est admis apres le nom de la ressource
  (/catalogue/accueil/<jeton>) et designe la meme ressource. La validation
  s'en sert pour partir d'une entree froide.
TXT
chown student:student "$WORK/contrat-de-contenu.txt"
chmod 0644 "$WORK/contrat-de-contenu.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 3 --silent --output /dev/null \
      http://127.0.0.1/catalogue/accueil; then
    echo "Situation posée : un catalogue mis en cache, et mal."
    exit 0
  fi
  sleep 1
done
echo "Nginx ne répond pas." >&2
exit 1
