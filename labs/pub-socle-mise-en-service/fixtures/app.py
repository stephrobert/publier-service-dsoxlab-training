"""Les deux origines du lab pub-socle-mise-en-service.

ROLE=origine, ORIGIN_ID=a   origine active, normale : sert /catalogue avec
                            le stock lu dans /var/lib/pub-mes/stock.json, et
                            /interne/compte, une route de gestion qui ne
                            doit jamais être atteignable depuis le client.
ROLE=origine, ORIGIN_ID=b   candidate de bascule, délibérément invalide :
                            /catalogue y répond toujours 500. Bascule dessus
                            pour observer un retour en arrière, jamais pour
                            la servir au client.

Les deux tournent en boucle locale sur edge.lab ; seul le routeur TLS
(``router.py``) leur fait face au client.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORIGIN_ID = os.environ["ORIGIN_ID"]
PORT = int(os.environ["PORT"])
STOCK = os.environ.get("STOCK", "/var/lib/pub-mes/stock.json")


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
        if self.path.startswith("/catalogue"):
            if ORIGIN_ID == "b":
                _repondre(self, 500, json.dumps({"erreur": "origine candidate invalide"}).encode())
                return
            try:
                with open(STOCK, encoding="utf-8") as fichier:
                    etat = json.load(fichier)
            except (FileNotFoundError, json.JSONDecodeError):
                _repondre(self, 500, json.dumps({"erreur": "etat indisponible"}).encode())
                return
            _repondre(
                self, 200,
                json.dumps({"origine": ORIGIN_ID, "stock": etat.get("stock")}).encode(),
            )
        elif self.path.startswith("/interne/compte"):
            _repondre(self, 200, json.dumps({"compte": f"secret-{ORIGIN_ID}"}).encode())
        else:
            _repondre(self, 404, json.dumps({"erreur": "route inconnue"}).encode())


def principal() -> None:
    ThreadingHTTPServer(("127.0.0.1", PORT), Gestionnaire).serve_forever()


if __name__ == "__main__":
    principal()
