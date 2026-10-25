"""Trois petits services pour le lab pub-socle-exposition.

ROLE=public   point d'entrée : relaie vers le backend sur 127.0.0.1
ROLE=backend  application : répond avec le nonce reçu
ROLE=admin    administration : répond « admin »
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["ROLE"]
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ["PORT"])
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "0"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _repondre(self, corps: bytes, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        nonce = self.headers.get("X-Nonce", "")
        if ROLE == "backend":
            self._repondre(json.dumps({"nom": "pub-backend", "nonce": nonce}).encode())
        elif ROLE == "admin":
            self._repondre(json.dumps({"nom": "pub-admin"}).encode())
        else:
            requete = urllib.request.Request(
                f"http://127.0.0.1:{BACKEND_PORT}/", headers={"X-Nonce": nonce}
            )
            with urllib.request.urlopen(requete, timeout=3) as reponse:
                self._repondre(reponse.read())


if __name__ == "__main__":
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
