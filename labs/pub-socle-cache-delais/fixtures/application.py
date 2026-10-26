#!/usr/bin/env python3
"""L'application metier du lab pub-socle-cache-delais.

Elle expose quatre comportements que le cache et les delais doivent traiter
correctement, et elle ne se protege d'aucun :

  GET  /public    reponse identique pour tous, mais qui VARIE selon la
                  langue demandee. Elle porte un numero de tirage, pour
                  qu'on sache si une reponse vient d'elle ou du cache.
  GET  /prive     la donnee de l'utilisateur, identifie par Authorization.
  POST /commande  action NON IDEMPOTENTE : elle incremente un compteur
                  metier, PUIS coupe la connexion sans repondre. C'est le
                  cas qui piege les rejeux automatiques.
  GET  /lent      repond au bout de deux secondes.
  GET  /panne     ne repond jamais.

LE COMPTEUR METIER EST LA PREUVE. Il vit dans un fichier, il est lisible par
la validation, et il dit combien de commandes ont REELLEMENT ete passees. Un
rejeu qui double une commande se voit la, et nulle part ailleurs : le client,
lui, n'a rien recu dans les deux cas.
"""

from __future__ import annotations

import json
import pathlib
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COMPTEUR = pathlib.Path("/opt/pub-socle-cache-delais/commandes.json")
VERROU = threading.Lock()
PORT = 18091

# Les donnees privees du banc, une par identite.
PRIVE = {
    "jeton-alice-3b21": "ALICE : commande 4821, adresse 12 rue des Lilas.\n",
    "jeton-bob-9d47": "BOB : commande 7735, adresse 3 impasse du Four.\n",
}


def _incrementer() -> int:
    with VERROU:
        etat = json.loads(COMPTEUR.read_text(encoding="utf-8"))
        etat["commandes"] = int(etat.get("commandes", 0)) + 1
        COMPTEUR.write_text(json.dumps(etat), encoding="utf-8")
        return etat["commandes"]


class Application(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/panne"):
            time.sleep(600)
            return
        if self.path.startswith("/lent"):
            time.sleep(2)
            self._repondre("LENT : la reponse est arrivee.\n")
            return
        if self.path.startswith("/prive"):
            jeton = (self.headers.get("Authorization", "")
                     .removeprefix("Bearer ").strip())
            self._repondre(PRIVE.get(jeton, "ANONYME : aucune donnee.\n"))
            return
        # /public : la langue change le contenu, et le tirage change a chaque
        # passage. Deux reponses identiques prouvent donc un cache, et deux
        # reponses differentes prouvent qu'il n'y en a pas.
        langue = self.headers.get("Accept-Language", "fr")
        self._repondre(
            f"PUBLIC [{langue}] tirage={random.randint(100000, 999999)}\n"
        )

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/commande"):
            total = _incrementer()
            # ECRIT PUIS COUPE. Le client ne saura pas si l'action a eu lieu :
            # c'est exactement la situation ou un rejeu automatique double la
            # commande.
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n")
            self.wfile.flush()
            self.close_connection = True
            self.connection.close()
            del total
            return
        self._repondre("METHODE SANS EFFET\n")

    def _repondre(self, corps: str) -> None:
        octets = corps.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(octets)))
        self.end_headers()
        self.wfile.write(octets)

    def log_message(self, *args):
        return


if __name__ == "__main__":
    COMPTEUR.parent.mkdir(parents=True, exist_ok=True)
    if not COMPTEUR.is_file():
        COMPTEUR.write_text(json.dumps({"commandes": 0}), encoding="utf-8")
    ThreadingHTTPServer(("127.0.0.1", PORT), Application).serve_forever()
