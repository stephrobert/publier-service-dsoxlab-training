"""Backend d'action jouet pour le lab pub-traefik-flux-delais, point testé
« post » (critique) : une action métier non idempotente ne doit pas être
dupliquée par une politique de retry.

- GET /compteur : rend la valeur courante du compteur (texte brut).
- POST /action  : incrémente durablement le compteur, PUIS, si
  /app/couper-une-fois existe, supprime ce fichier et ferme la connexion
  TCP brutalement SANS envoyer de réponse HTTP, simulant une réponse
  perdue après une écriture déjà réussie côté serveur. Sans ce fichier,
  répond normalement 200 avec la nouvelle valeur du compteur.

Le compteur est un fichier texte simple : il doit survivre à la coupure
de connexion, puisque l'écriture a lieu AVANT la coupure.
"""

from __future__ import annotations

import http.server
import os
import socket
import socketserver

COUNTER_FILE = "/app/compteur"
TOGGLE_FILE = "/app/couper-une-fois"


def _lire_compteur() -> int:
    try:
        with open(COUNTER_FILE, encoding="utf-8") as fichier:
            return int(fichier.read().strip() or "0")
    except (FileNotFoundError, ValueError):
        return 0


def _ecrire_compteur(valeur: int) -> None:
    with open(COUNTER_FILE, "w", encoding="utf-8") as fichier:
        fichier.write(str(valeur))
        fichier.flush()
        os.fsync(fichier.fileno())


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/compteur":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(_lire_compteur()).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/action":
            self.send_response(404)
            self.end_headers()
            return

        valeur = _lire_compteur() + 1
        _ecrire_compteur(valeur)

        if os.path.exists(TOGGLE_FILE):
            os.remove(TOGGLE_FILE)
            # L'écriture ci-dessus est déjà durable : la coupure qui suit
            # ne doit JAMAIS l'annuler, elle simule seulement la perte du
            # trajet retour de la réponse.
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(str(valeur).encode())

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    with socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        httpd.serve_forever()
