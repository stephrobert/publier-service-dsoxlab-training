#!/usr/bin/env python3
"""Application de catalogue du lab : page statique, API et dépendance de stock."""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ["APP_PORT"])
STOCK_PORT = int(os.environ["STOCK_PORT"])
TITRE = os.environ["APP_TITRE"]
COMPTEUR = os.path.join(os.environ["STATE_DIRECTORY"], "visites")
visites_memoire = 0


def visites_disque() -> int:
    try:
        with open(COMPTEUR, encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except FileNotFoundError:
        return 0


class Handler(BaseHTTPRequestHandler):
    def _reponse(self, code, corps, type_mime="application/json"):
        donnees = corps.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def do_GET(self):
        global visites_memoire
        if self.path == "/":
            visites_memoire += 1
            with open(COMPTEUR, "w", encoding="utf-8") as f:
                f.write(str(visites_disque() + 1))
            self._reponse(200, f"<h1>{TITRE}</h1>", "text/html")
        elif self.path == "/health":
            self._reponse(200, '{"status": "ok"}')
        elif self.path == "/api/etat":
            self._reponse(200, json.dumps({"visites_disque": visites_disque(),
                                           "visites_memoire": visites_memoire}))
        elif self.path == "/api/livres":
            try:
                url = f"http://127.0.0.1:{STOCK_PORT}/stock"
                with urllib.request.urlopen(url, timeout=2) as reponse:
                    self._reponse(200, reponse.read().decode("utf-8"))
            except OSError:
                self._reponse(503, '{"error": "stock indisponible"}')
        else:
            self._reponse(404, '{"error": "inconnu"}')

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
