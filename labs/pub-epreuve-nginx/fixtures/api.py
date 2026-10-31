"""L'API du catalogue de l'épreuve pub-epreuve-nginx.

Un seul processus, sur la boucle locale, qui joue plusieurs rôles à la fois
parce que l'épreuve en demande plusieurs :

  /v1/valeur   public, cacheable (max-age=600) ; chaque fabrication de corps
               est COMPTÉE, ce qui permet de mesurer un cache à l'origine
               plutôt que de croire un en-tête.
  /v1/echo     renvoie le nonce reçu ; jamais cacheable.
  /v1/lent     met deux secondes à répondre : sert à vérifier qu'un journal
               mesure vraiment.
  /v1/flux     six événements SSE, un par seconde.
  /v1/compte   privé : réponse propre à la session du cookie `session`.
  /admin       console d'administration. Le backend fait confiance à son
               proxy : c'est le proxy qui doit refuser.
  /_compteur   compteurs de fabrication, pour la validation.

Toute méthode est acceptée sur /v1/valeur : c'est au proxy de refuser celles
dont le service n'a pas besoin.

Après un redéploiement du backend (variante d'incident « entêtes »), le
fichier DONNEES/exige-host fait refuser toute requête dont l'en-tête Host
n'est pas le nom public de l'API.
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PORT = int(os.environ.get("PORT", "18201"))
ADRESSE = os.environ.get("ADRESSE", "127.0.0.1")
DONNEES = os.environ.get("DONNEES", "/var/lib/pub-epn")
NOM_API = "api.epreuve.test"
VERROU = threading.Lock()
FABRICATIONS = {"valeur": 0, "compte": 0}


def lire(nom: str) -> str:
    with open(os.path.join(DONNEES, nom), encoding="utf-8") as fichier:
        return fichier.read().strip()


class Api(BaseHTTPRequestHandler):
    server_version = "catalogue/1"

    def _repondre(self, code: int, corps: bytes, entetes: dict[str, str]) -> None:
        self.send_response(code)
        for cle, valeur in entetes.items():
            self.send_header(cle, valeur)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corps)

    def _json(self, code: int, objet: dict, cache: str) -> None:
        self._repondre(
            code,
            (json.dumps(objet) + "\n").encode(),
            {"Content-Type": "application/json", "Cache-Control": cache},
        )

    def _host_refuse(self) -> bool:
        """Le backend redéployé n'accepte plus que son nom public."""
        if not os.path.exists(os.path.join(DONNEES, "exige-host")):
            return False
        host = (self.headers.get("Host") or "").split(":", 1)[0].lower()
        return host != NOM_API

    def _servir(self) -> None:
        if self._host_refuse():
            self._json(
                421,
                {"erreur": "host inattendu", "attendu": NOM_API},
                "no-store",
            )
            return

        url = urlsplit(self.path)
        chemin = url.path
        requete = parse_qs(url.query)

        if chemin == "/_compteur":
            with VERROU:
                corps = dict(FABRICATIONS)
            self._json(200, corps, "no-store")
            return

        if chemin == "/v1/valeur":
            with VERROU:
                FABRICATIONS["valeur"] += 1
            valeur = json.loads(lire("donnees.json"))["valeur"]
            self._json(
                200,
                {"valeur": valeur, "methode": self.command},
                "public, max-age=600",
            )
            return

        if chemin == "/v1/echo":
            nonce = (requete.get("nonce") or [""])[0]
            self._json(200, {"nonce": nonce}, "no-store")
            return

        if chemin == "/v1/lent":
            time.sleep(2)
            self._json(200, {"lent": True}, "no-store")
            return

        if chemin == "/v1/flux":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            for numero in range(1, 7):
                self.wfile.write(f"data: evenement-{numero}\n\n".encode())
                self.wfile.flush()
                time.sleep(1)
            return

        if chemin == "/v1/compte":
            session = ""
            for morceau in (self.headers.get("Cookie") or "").split(";"):
                morceau = morceau.strip()
                if morceau.startswith("session="):
                    session = morceau[len("session="):]
            if session not in ("alpha", "beta"):
                self._json(401, {"erreur": "session requise"}, "private, no-store")
                return
            with VERROU:
                FABRICATIONS["compte"] += 1
            self._repondre(
                200,
                (
                    json.dumps(
                        {"compte": session, "marqueur": lire(f"marqueur-{session}.txt")}
                    )
                    + "\n"
                ).encode(),
                {
                    "Content-Type": "application/json",
                    "Cache-Control": "private, no-store",
                    "Set-Cookie": "vu=1; Path=/",
                },
            )
            return

        if chemin == "/admin" or chemin.startswith("/admin/"):
            self._json(
                200,
                {"console": "administration", "secret": lire("secret-admin.txt")},
                "no-store",
            )
            return

        self._json(404, {"erreur": "introuvable"}, "no-store")

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = _servir

    def log_message(self, *args) -> None:
        return


def main() -> None:
    serveur = ThreadingHTTPServer((ADRESSE, PORT), Api)
    # Le port réellement écouté est publié pour la validation : une variante
    # d'incident peut le déplacer, et un test ne doit pas le deviner.
    try:
        with open("/run/pub-epn/api.port", "w", encoding="utf-8") as fichier:
            fichier.write(f"{PORT}\n")
    except OSError:
        pass
    serveur.serve_forever()


if __name__ == "__main__":
    main()
