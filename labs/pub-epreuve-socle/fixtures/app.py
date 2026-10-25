"""Le backend du lab pub-epreuve-socle.

Deux routes, fixées dans le code :

``/``        route métier publique. Sert les données lues dans
             ``DONNEES`` (JSON), jamais une valeur par défaut : si le
             fichier manque, répond 500 plutôt que d'inventer un contenu.
``/admin``   route d'administration, refusée en toutes circonstances.

Écoute en boucle locale (127.0.0.1) : jamais censé être joignable
directement depuis le client. Seul le routeur TLS (``router.py``) lui fait
face.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ["PORT"])
DONNEES = os.environ.get("DONNEES", "/var/lib/pub-eps/donnees.json")


def _repondre(gestionnaire: BaseHTTPRequestHandler, code: int, corps: bytes) -> None:
    gestionnaire.send_response(code)
    gestionnaire.send_header("Content-Type", "application/json")
    gestionnaire.send_header("Content-Length", str(len(corps)))
    gestionnaire.end_headers()
    gestionnaire.wfile.write(corps)


class Gestionnaire(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith("/admin"):
            _repondre(self, 403, json.dumps({"erreur": "route interne refusee"}).encode())
            return
        if self.path == "/" or self.path.startswith("/?"):
            try:
                with open(DONNEES, encoding="utf-8") as fichier:
                    etat = json.load(fichier)
            except (FileNotFoundError, json.JSONDecodeError):
                _repondre(self, 500, json.dumps({"erreur": "donnees indisponibles"}).encode())
                return
            nonce = None
            if "?nonce=" in self.path:
                nonce = self.path.split("?nonce=", 1)[1]
            corps = {"service": "ok", "valeur": etat.get("valeur")}
            if nonce:
                corps["nonce"] = nonce
            _repondre(self, 200, json.dumps(corps).encode())
        else:
            _repondre(self, 404, json.dumps({"erreur": "route inconnue"}).encode())


def principal() -> None:
    ThreadingHTTPServer(("127.0.0.1", PORT), Gestionnaire).serve_forever()


if __name__ == "__main__":
    principal()
