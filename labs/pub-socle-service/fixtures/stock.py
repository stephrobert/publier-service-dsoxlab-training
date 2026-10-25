#!/usr/bin/env python3
"""Dépendance simulée du lab : le service de stock lu par l'application."""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ["STOCK_PORT"])
LIVRES = os.environ["LIVRES_FICHIER"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stock":
            with open(LIVRES, "rb") as f:
                donnees = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
