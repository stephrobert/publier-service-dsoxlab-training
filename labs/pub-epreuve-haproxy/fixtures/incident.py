#!/usr/bin/env python3
"""Les quatre backends de l'instance « archives » de pub-epreuve-haproxy.

Un seul processus, quatre ecoutes, et chacune existe pour rendre UNE mesure
possible :

  - `web` (18311)       l'application saine. Marqueur `archives-web`.
  - `degrade` (18312)   vivant au niveau TCP, mais sa readiness echoue et ses
                        routes utiles rendent 500. C'est la panne qu'une
                        sonde existe pour voir : il doit rester hors service.
  - `api` (18313, TLS)  le backend legitime. Marqueur `archives-api`, et deux
                        routes lentes : `/v2/lent` (3 s) que la borne saine
                        laisse passer, et `/v2/bloque` (25 s) qu'elle doit
                        couper.
  - `imposteur` (18314, TLS)  meme nom, meme marqueur, mais un certificat signe
                        par une autorite etrangere. Si la verification TLS est
                        desactivee, sa reponse est indiscernable d'un succes.

Usage : incident.py <pki>
"""

from __future__ import annotations

import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PKI = sys.argv[1]


def fabriquer(marqueur: str, degrade: bool):
    class Service(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _rendre(self, statut: int, corps: bytes) -> None:
            self.send_response(statut)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)

        def do_GET(self) -> None:  # noqa: N802 - nom impose par http.server
            if self.path.startswith("/sante"):
                # Une route qui n'existe nulle part : c'est elle que la
                # variante « sonde » fait interroger a la place de /ready.
                self._rendre(404, b"inconnu\n")
                return
            if self.path.startswith("/ready"):
                if degrade:
                    self._rendre(503, b"pas pret\n")
                else:
                    self._rendre(200, b"pret\n")
                return
            if degrade:
                self._rendre(500, b"degrade en echec\n")
                return
            if self.path.startswith("/v2/lent"):
                time.sleep(3)
            elif self.path.startswith("/v2/bloque"):
                time.sleep(25)
            self._rendre(200, f"{marqueur}\nchemin: {self.path}\n".encode())

        def log_message(self, *args) -> None:
            return

    return Service


class Serveur(ThreadingHTTPServer):
    """Un serveur TLS qui ne fait pas son handshake dans l'accept().

    Enveloppe sur le socket d'ECOUTE, le handshake a lieu dans accept(), donc
    dans le thread d'accueil : une connexion dont le handshake n'avance pas
    bloque toutes les autres, qui s'empilent dans le backlog puis sont
    refusees. HAProxy sonde ce service chaque seconde ET y envoie du trafic :
    il le verrait UP et recevrait `SC--` sur le trafic. On accepte donc en
    clair, ce qui est immediat, et le handshake se joue dans le thread de
    traitement.
    """

    daemon_threads = True
    request_queue_size = 128
    allow_reuse_address = True
    contexte = None

    def process_request_thread(self, request, client_address):
        if self.contexte is not None:
            try:
                request = self.contexte.wrap_socket(request, server_side=True)
            except OSError as erreur:
                # Un handshake refuse est le cas NORMAL de cette instance :
                # le canari presente exprès un mauvais certificat. Il ne doit
                # pas emporter le service, mais il se DIT.
                print(
                    f"handshake refuse pour {client_address}: "
                    f"{type(erreur).__name__}: {erreur}",
                    file=sys.stderr,
                    flush=True,
                )
                self.shutdown_request(request)
                return
        super().process_request_thread(request, client_address)


def servir(port: int, marqueur: str, degrade: bool, cert: str = "", cle: str = ""):
    serveur = Serveur(("127.0.0.1", port), fabriquer(marqueur, degrade))
    if cert:
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexte.load_cert_chain(cert, cle)
        serveur.contexte = contexte
    serveur.serve_forever()


if __name__ == "__main__":
    for port, marqueur, degrade, cert, cle in (
        (18311, "archives-web", False, "", ""),
        (18312, "archives-degrade", True, "", ""),
        (18313, "archives-api", False, f"{PKI}/api.crt", f"{PKI}/api.key"),
        (18314, "archives-api", False, f"{PKI}/imposteur.crt", f"{PKI}/imposteur.key"),
    ):
        threading.Thread(
            target=servir, args=(port, marqueur, degrade, cert, cle), daemon=True
        ).start()
    while True:
        time.sleep(3600)
