"""Petit site web à double pile : répond « <version>-<jeton> » en IPv4 et en IPv6."""

import socket
import sys
import time
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


def lier(classe, adresse: str, limite_s: float = 45.0):
    """Ouvre l'ecoute, en laissant l'adresse devenir liable.

    UNE ADRESSE QUI EXISTE N'EST PAS ENCORE UTILISABLE. Une adresse IPv6
    fraichement posee reste en etat « tentative » le temps de la detection
    de doublon, et s'y lier sort en EADDRNOTAVAIL.
    `After=network-online.target` ne couvre pas ce delai.

    Sans cette attente, l'unite echouait au demarrage, redemarrait en
    boucle, et systemd finissait par la bloquer sur son quota : les deux
    sites du banc etaient morts et le lab accusait le DNS (mesure du
    2026-10-26, « the client sees '' »).
    """
    fin = time.monotonic() + limite_s
    derniere = None
    while time.monotonic() < fin:
        try:
            return classe((adresse, 80), Reponse)
        except OSError as erreur:
            derniere = erreur
            time.sleep(1)
    raise SystemExit(f"impossible de se lier a {adresse}:80 apres "
                     f"{limite_s:.0f} s : {derniere}")


serveurs = [
    lier(ThreadingHTTPServer, adresse4),
    lier(Serveur6, adresse6),
]
for s in serveurs[1:]:
    threading.Thread(target=s.serve_forever, daemon=True).start()
serveurs[0].serve_forever()
