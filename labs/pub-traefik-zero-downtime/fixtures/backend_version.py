"""Backend jouet versionné pour le lab pub-traefik-zero-downtime.

Chaque instance sert une seule version (VERSION=v1 ou VERSION=v2) et lit
son état de santé dans un fichier marqueur, posé ou retiré par
`docker exec ... touch|rm /app/healthy` (même convention que
pub-traefik-flux-delais) :

- GET /health  : 200 « ok » si /app/healthy existe, 503 sinon.
- GET /        : si /app/healthy existe, 200 avec le corps
  « version=<VERSION> » (identité réellement observable dans le trafic,
  pas seulement sur la sonde) ; sinon 500, pour qu'une version malsaine
  restée en rotation produise une vraie erreur mesurable, pas une
  dégradation silencieuse.

Stdlib uniquement : aucune dépendance à installer dans l'image.
"""

from __future__ import annotations

import http.server
import os
import socketserver

HEALTH_FILE = "/app/healthy"
VERSION = os.environ.get("VERSION", "inconnue")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (API imposée par http.server)
        sain = os.path.exists(HEALTH_FILE)
        if self.path == "/health":
            self.send_response(200 if sain else 503)
            self.end_headers()
            self.wfile.write(b"ok" if sain else b"unhealthy")
            return
        if not sain:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"version={VERSION} unhealthy".encode())
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"version={VERSION}".encode())

    def log_message(self, *args: object) -> None:  # silence l'accès-log
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        httpd.serve_forever()
