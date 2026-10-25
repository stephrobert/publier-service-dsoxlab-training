"""Point d'entrée TLS, application backend et deux pages d'origine, pour le
lab pub-socle-application.

ROLE=entree    seul maillon joignable (en pratique par le navigateur
               automatisable fourni, qui tourne sur ce même hôte), termine
               TLS, relaie en HTTP clair vers l'application. C'est lui qui
               décide, selon la politique, s'il annonce lui-même le schéma
               réel à l'application (X-Forwarded-Proto) et s'il calcule
               l'identité depuis le cookie de session validé plutôt que de
               reconduire un en-tête d'identité déjà porté par le client.
ROLE=backend   l'application : connexion, session, cookie et politique
               d'origine. Elle ne voit jamais le client directement, elle
               ne reçoit que ce que l'entree lui transmet.
ROLE=origine   une page statique minimale, servie en clair sur un port qui
               lui est propre : son seul rôle est de représenter une
               origine de navigateur distincte (un port différent suffit)
               et d'y exécuter une requête pré-vol puis réelle vers
               l'application, pour que la politique d'origine soit
               observée depuis l'endroit où elle s'applique réellement.

Les trois rôles tournent sur edge.lab, en boucle locale : le navigateur
automatisable fourni tourne sur ce même hôte, il n'y a donc pas besoin
d'exposer quoi que ce soit au-delà de 127.0.0.1.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import ssl
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["ROLE"]
PORT = int(os.environ["PORT"])
POLITIQUE = os.environ.get("POLITIQUE", "/etc/pub-app/politique.yaml")
SECRET = os.environ.get("SECRET", "")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "0"))
ENTREE_PORT = int(os.environ.get("ENTREE_PORT", "0"))
ORIGINE_NOM = os.environ.get("ORIGINE_NOM", "")

USAGERS = {"etudiant": "motdepasse-correct"}


def _charger_politique() -> dict:
    import yaml

    try:
        with open(POLITIQUE, encoding="utf-8") as fichier:
            return yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return {}


def _signature(usager: str) -> str:
    return hmac.new(
        SECRET.encode(), usager.encode(), hashlib.sha256
    ).hexdigest()[:12]


def _valeur_cookie(usager: str) -> str:
    return f"{usager}.{_signature(usager)}"


def _usager_depuis_cookie(cookie_entete: str | None) -> str | None:
    if not cookie_entete:
        return None
    for morceau in cookie_entete.split(";"):
        morceau = morceau.strip()
        if not morceau.startswith("session="):
            continue
        valeur = morceau[len("session=") :]
        if "." not in valeur:
            return None
        usager, signature = valeur.rsplit(".", 1)
        if hmac.compare_digest(signature, _signature(usager)):
            return usager
        return None
    return None


class Gestionnaire(BaseHTTPRequestHandler):
    # HTTP/1.0 : la connexion se ferme après chaque réponse, comme dans les
    # autres labs de cette série.
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    # -- utilitaires communs ------------------------------------------------

    def _lire_corps(self) -> bytes:
        longueur = int(self.headers.get("Content-Length", "0") or "0")
        return self.rfile.read(longueur) if longueur else b""

    def _repondre(
        self,
        code: int,
        corps: bytes,
        entetes: dict[str, str] | None = None,
        content_type: str = "application/json",
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(corps)))
        for cle, valeur in (entetes or {}).items():
            self.send_header(cle, valeur)
        self.end_headers()
        if corps:
            self.wfile.write(corps)

    def do_GET(self):
        if ROLE == "entree":
            self._relayer("GET")
        elif ROLE == "origine":
            self._page_origine()
        else:
            self._backend_get()

    def do_POST(self):
        if ROLE == "entree":
            self._relayer("POST")
        else:
            self._backend_post()

    def do_OPTIONS(self):
        if ROLE == "entree":
            self._relayer("OPTIONS")
        else:
            self._backend_options()

    # -- ROLE=entree ----------------------------------------------------

    def _relayer(self, methode: str) -> None:
        """Seul maillon joignable : décide schéma et identité transmis."""
        politique = _charger_politique()
        corps = self._lire_corps() if methode == "POST" else b""

        entetes = {}
        for cle in ("Content-Type", "Content-Length", "Origin", "Cookie", "Host"):
            if cle in self.headers:
                entetes[cle] = self.headers[cle]

        if (politique.get("entete_proto") or {}).get("transmettre"):
            # L'entree termine toujours TLS ici : l'affirmation est vraie.
            entetes["X-Forwarded-Proto"] = "https"

        if (politique.get("identite") or {}).get("faire_confiance_entete_client"):
            # Repli bogué : un en-tête d'identité déjà présent est reconduit
            # tel quel, sans jamais regarder la session.
            if "X-Pub-User" in self.headers:
                entetes["X-Pub-User"] = self.headers["X-Pub-User"]
        else:
            # L'entree décide elle-même, depuis le cookie de session
            # validé : un en-tête client est ignoré purement et simplement.
            usager = _usager_depuis_cookie(self.headers.get("Cookie"))
            if usager:
                entetes["X-Pub-User"] = usager

        connexion = http.client.HTTPConnection("127.0.0.1", BACKEND_PORT, timeout=3)
        try:
            connexion.request(methode, self.path, body=corps or None, headers=entetes)
            reponse = connexion.getresponse()
            corps_reponse = reponse.read()
            entetes_reponse = {}
            for cle, valeur in reponse.getheaders():
                if cle.lower() in ("content-length", "transfer-encoding", "connection"):
                    continue
                entetes_reponse[cle] = valeur
            self._repondre(
                reponse.status,
                corps_reponse,
                entetes_reponse,
                content_type=entetes_reponse.pop("Content-Type", "application/json"),
            )
        finally:
            connexion.close()

    # -- ROLE=backend -----------------------------------------------------

    def _assurer_https(self) -> bool:
        """Renvoie True si la requête doit continuer, False si elle a été
        redirigée. Bogue initial : sans l'en-tête transmis par l'entree,
        ceci redirige systématiquement, y compris quand le client est déjà
        en HTTPS, ce qui boucle indéfiniment."""
        if self.headers.get("X-Forwarded-Proto") == "https":
            return True
        hote = self.headers.get("Host", "127.0.0.1")
        self._repondre(
            302,
            b"",
            {"Location": f"https://{hote}{self.path}"},
            content_type="text/plain",
        )
        return False

    def _backend_get(self) -> None:
        if self.path == "/login":
            self._repondre(
                200,
                _PAGE_LOGIN.encode(),
                content_type="text/html; charset=utf-8",
            )
            return
        if self.path == "/api/identite":
            # Route protégée indépendante de /compte : elle ne vérifie que
            # l'identité, pas le schéma, pour isoler ce point du bogue de
            # boucle de redirection.
            usager = self.headers.get("X-Pub-User", "")
            identite = usager if usager in USAGERS else "anonyme"
            self._repondre(200, json.dumps({"identite": identite}).encode())
            return
        if self.path == "/compte":
            if not self._assurer_https():
                return
            usager = self.headers.get("X-Pub-User", "")
            if usager and usager in USAGERS:
                corps = f"<h1>Bonjour {usager}</h1><p>compte: connecte</p>"
            else:
                corps = "<h1>Non connecte</h1><p>compte: anonyme</p>"
            self._repondre(200, corps.encode(), content_type="text/html; charset=utf-8")
            return
        self._repondre(404, b"{}")

    def _backend_post(self) -> None:
        if self.path == "/api/question":
            self._backend_post_question()
            return
        if self.path != "/login":
            self._repondre(404, b"{}")
            return
        corps = self._lire_corps().decode()
        champs = urllib.parse.parse_qs(corps)
        usager = (champs.get("usager") or [""])[0]
        motdepasse = (champs.get("motdepasse") or [""])[0]
        if USAGERS.get(usager) != motdepasse:
            self._repondre(401, b'{"erreur":"identifiants invalides"}')
            return
        politique = _charger_politique()
        domaine = (politique.get("cookie") or {}).get("domaine", "")
        attributs = f"session={_valeur_cookie(usager)}; Path=/; HttpOnly"
        if domaine:
            attributs += f"; Domain={domaine}"
        self._repondre(
            302,
            b"",
            {"Location": "/compte", "Set-Cookie": attributs},
            content_type="text/plain",
        )

    def _origine_autorisee(self, origine: str | None) -> str | None:
        politique = _charger_politique()
        cors = politique.get("cors") or {}
        if not origine:
            return None
        if cors.get("autoriser_toutes_origines"):
            # Repli bogué : toute origine reçoit l'autorisation.
            return origine
        if origine == cors.get("origine_autorisee"):
            return origine
        return None

    def _backend_options(self) -> None:
        if self.path != "/api/question":
            self._repondre(404, b"{}")
            return
        autorisee = self._origine_autorisee(self.headers.get("Origin"))
        entetes = {
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "60",
        }
        if autorisee:
            entetes["Access-Control-Allow-Origin"] = autorisee
        self._repondre(204, b"", entetes, content_type="text/plain")

    def _backend_post_question(self) -> None:
        autorisee = self._origine_autorisee(self.headers.get("Origin"))
        entetes = {}
        if autorisee:
            entetes["Access-Control-Allow-Origin"] = autorisee
        self._repondre(200, b'{"reponse":"ok"}', entetes)

    # -- ROLE=origine -------------------------------------------------------

    def _page_origine(self) -> None:
        page = _PAGE_ORIGINE.replace("__NOM__", ORIGINE_NOM).replace(
            "__ENTREE_PORT__", str(ENTREE_PORT)
        )
        self._repondre(200, page.encode(), content_type="text/html; charset=utf-8")


_PAGE_LOGIN = """<!doctype html>
<html lang="fr">
<body>
<form method="post" action="/login">
  <input name="usager" value="etudiant">
  <input name="motdepasse" type="password" value="motdepasse-correct">
  <button type="submit">Connexion</button>
</form>
</body>
</html>"""


_PAGE_ORIGINE = """<!doctype html>
<html lang="fr">
<body>
<div id="resultat">en-cours</div>
<script>
async function tenter() {
  try {
    const reponse = await fetch("https://127.0.0.1:__ENTREE_PORT__/api/question", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({depuis: "__NOM__"}),
    });
    const corps = await reponse.text();
    document.getElementById("resultat").innerText = JSON.stringify({
      ok: true, statut: reponse.status, corps: corps,
    });
  } catch (erreur) {
    document.getElementById("resultat").innerText = JSON.stringify({
      ok: false, erreur: String(erreur),
    });
  }
}
tenter();
</script>
</body>
</html>"""


def principal() -> None:
    serveur = ThreadingHTTPServer(("127.0.0.1", PORT), Gestionnaire)
    if ROLE == "entree":
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexte.load_cert_chain(os.environ["TLS_CERT"], os.environ["TLS_KEY"])
        serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
    serveur.serve_forever()


if __name__ == "__main__":
    principal()
