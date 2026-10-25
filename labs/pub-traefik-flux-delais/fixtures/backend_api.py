"""Backend API jouet pour le lab pub-traefik-flux-delais.

Expose trois routes utiles aux points testés « délais » et « retrait » :

- GET /health   : 200 si /app/healthy existe, 503 sinon. La sonde de
  santé Traefik et les tests du lab basculent cet état via `docker exec`.
- GET /lent      : attend `ms` millisecondes (paramètre de requête) avant
  de répondre 200. Une lenteur bornée doit réussir. Refuse (503) si
  /app/healthy est absent : un backend « malade » l'est réellement, pas
  seulement sur sa sonde, sinon retirer ou non de la rotation ne changerait
  jamais rien d'observable.
- GET /bloque    : ne répond jamais (le processus dort). Simule une panne
  persistante : le serveur HTTP est threadé, une requête bloquée ici
  n'empêche pas les autres de répondre.

Stdlib uniquement : aucune dépendance à installer dans l'image.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import time
import urllib.parse

HEALTH_FILE = "/app/healthy"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (API imposée par http.server)
        chemin = urllib.parse.urlparse(self.path)
        if chemin.path == "/health":
            if os.path.exists(HEALTH_FILE):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"unhealthy")
        elif chemin.path == "/lent":
            if not os.path.exists(HEALTH_FILE):
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"unhealthy")
                return
            params = urllib.parse.parse_qs(chemin.query)
            ms = int(params.get("ms", ["0"])[0])
            if ms > 0:
                time.sleep(ms / 1000)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok-lent")
        elif chemin.path == "/bloque":
            time.sleep(600)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args: object) -> None:  # silence l'accès-log
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        httpd.serve_forever()
