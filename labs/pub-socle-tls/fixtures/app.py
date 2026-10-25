"""Petit serveur HTTPS pour le lab pub-socle-tls.

Un seul rôle : accepter une connexion TLS avec le certificat et la clé
fournis en arguments, puis répondre un corps fixe. Le certificat et la
confiance qu'il obtient sont entièrement décidés par `prepare.sh`, jamais par
ce script : il ne fait que servir ce qu'on lui donne.
"""

from __future__ import annotations

import ssl
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def main() -> None:
    nom, port_s, certfile, keyfile = sys.argv[1:5]
    port = int(port_s)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (nom imposé par BaseHTTPRequestHandler)
            corps = f"pub-tls-ok {nom}\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    httpd = HTTPServer(("0.0.0.0", port), Handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
