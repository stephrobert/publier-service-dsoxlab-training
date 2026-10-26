#!/usr/bin/env python3
"""L'application metier du lab pub-socle-securite.

Elle sert trois routes et ne protege RIEN : c'est au garde de le faire, selon
la politique. Une application qui se protegerait elle-meme rendrait le lab
vert sans politique, et il n'enseignerait plus rien.

Son adresse d'ecoute est lue dans l'environnement, parce que la refermer sur
la boucle locale est l'un des deux gestes qui ferment l'acces direct. L'autre
est un filtrage reseau, et les deux sont acceptes.
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ADRESSE = os.environ.get("ADRESSE", "0.0.0.0")  # noqa: S104
PORT = int(os.environ.get("PORT", "18090"))

CONTENUS = {
    "/admin": "ADMINISTRATION : revocation des acces, purge des journaux.\n",
    "/compte": "COMPTE : solde, adresse de livraison, historique des commandes.\n",
    "/": "PUBLIC : horaires, tarifs, contact.\n",
}


class Application(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        corps = "PUBLIC : horaires, tarifs, contact.\n"
        for prefixe, contenu in CONTENUS.items():
            if self.path.startswith(prefixe):
                corps = contenu
                break
        octets = corps.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(octets)))
        self.end_headers()
        self.wfile.write(octets)

    def log_message(self, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer((ADRESSE, PORT), Application).serve_forever()
