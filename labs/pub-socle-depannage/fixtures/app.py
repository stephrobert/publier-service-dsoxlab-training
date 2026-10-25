"""Le backend du lab pub-socle-depannage.

Deux routes, fixées dans le code et jamais pilotées par une configuration
modifiable :

``/``        route métier publique, répond 200.
``/admin``   route d'administration, répond 403 en toutes circonstances :
             ce refus est une propriété de sécurité du service, pas un
             symptôme de la panne à corriger.

Le backend écoute en boucle locale (127.0.0.1) : il n'est jamais censé être
joignable directement depuis le client. Seul le routeur TLS (``router.py``)
lui fait face.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ["PORT"])


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
        elif self.path == "/" or self.path.startswith("/?"):
            _repondre(self, 200, json.dumps({"service": "ok"}).encode())
        else:
            _repondre(self, 404, json.dumps({"erreur": "route inconnue"}).encode())


def principal() -> None:
    ThreadingHTTPServer(("127.0.0.1", PORT), Gestionnaire).serve_forever()


if __name__ == "__main__":
    principal()
