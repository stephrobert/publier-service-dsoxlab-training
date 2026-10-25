"""Backend minimal du lab pub-socle-dns-http-tls.

Répond toujours "<nom>-<jeton>" : les tests l'utilisent pour savoir quelle
application a réellement répondu, sans jamais faire confiance au texte de la
fiche de l'apprenant.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

nom, jeton, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
CORPS = f"{nom}-{jeton}\n".encode()


class Reponse(BaseHTTPRequestHandler):
    # HTTP/1.0 : la connexion se ferme après chaque réponse, ce qui évite au
    # routeur de devoir gérer le maintien de connexion (keep-alive).
    protocol_version = "HTTP/1.0"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(CORPS)))
        self.end_headers()
        self.wfile.write(CORPS)

    def log_message(self, *_):
        pass


ThreadingHTTPServer(("127.0.0.1", port), Reponse).serve_forever()
