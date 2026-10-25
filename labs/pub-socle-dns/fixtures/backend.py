"""Petit site web à double pile : répond « <version>-<jeton> » en IPv4 et en IPv6."""

import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

version, jeton, adresse4, adresse6 = sys.argv[1:5]
CORPS = f"{version}-{jeton}\n".encode()


class Reponse(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(CORPS)))
        self.end_headers()
        self.wfile.write(CORPS)

    def log_message(self, *_):
        pass


class Serveur6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


serveurs = [
    ThreadingHTTPServer((adresse4, 80), Reponse),
    Serveur6((adresse6, 80), Reponse),
]
for s in serveurs[1:]:
    threading.Thread(target=s.serve_forever, daemon=True).start()
serveurs[0].serve_forever()
