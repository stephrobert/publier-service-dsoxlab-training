#!/usr/bin/env python3
"""Les deux services de pub-epreuve-haproxy : `catalogue` et `notifications`.

Un seul fichier, lance une fois par service (`services.py <nom>`), avec
`BIND`, `PORT` et `DONNEES` dans l'environnement de l'unite systemd.

CE QUE LES SERVICES RENVOIENT, ET POURQUOI

Chaque reponse JSON porte le NOM du service, le `nonce` demande dans la
requete et les en-tetes que le proxy a transmis. Sans cet echo, « le bon
backend a repondu » et « l'adresse source est celle du client » seraient des
affirmations du proxy qu'il faudrait croire sur parole. Ici le BACKEND les
dit, et le test les lit.

`X-Forwarded-For` est renvoye avec TOUTES ses occurrences : HAProxy ajoute une
ligne d'en-tete de plus quand le client en a deja envoye une, et une
application qui ne lit que la premiere voit l'adresse que le client a choisie.

Le backend ne protege RIEN lui-meme : `/admin` est servi a qui le demande.
C'est au point d'entree de refuser, et c'est ce que le test mesure.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

NOM = sys.argv[1]
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ["PORT"])
DONNEES = os.environ.get("DONNEES", "")

# Le silence entre deux evenements du flux est LONG a dessein : c'est lui qui
# met a l'epreuve les bornes d'inactivite du proxy. Une borne de 30 secondes,
# valeur courante des exemples, coupe ce flux entre le premier et le deuxieme
# evenement.
BATTEMENT = 35
DUREE_FLUX = 75


class Service(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, statut: int, charge: dict) -> None:
        corps = (json.dumps(charge) + "\n").encode()
        self.send_response(statut)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _base(self, chemin: str, nonce: str) -> dict:
        return {
            "service": NOM,
            "nonce": nonce,
            "chemin": chemin,
            "host": self.headers.get("Host", "absent"),
            "xff": ", ".join(self.headers.get_all("X-Forwarded-For") or ["absent"]),
            "proto": ", ".join(self.headers.get_all("X-Forwarded-Proto") or ["absent"]),
        }

    def do_GET(self) -> None:  # noqa: N802 - nom impose par http.server
        url = urlsplit(self.path)
        requete = parse_qs(url.query)
        chemin = url.path
        nonce = requete.get("nonce", [""])[0]
        base = self._base(chemin, nonce)

        if chemin == "/pret":
            self._json(200, {"pret": True, "service": NOM})
            return

        if chemin.startswith("/admin"):
            base["administration"] = True
            self._json(200, base)
            return

        if chemin == "/api/produits" and NOM == "catalogue":
            try:
                with open(DONNEES, encoding="utf-8") as fichier:
                    donnees = json.load(fichier)
            except (OSError, ValueError):
                base["erreur"] = "donnees absentes"
                self._json(503, base)
                return
            base.update(donnees)
            self._json(200, base)
            return

        if chemin == "/flux" and NOM == "notifications":
            self._flux(requete)
            return

        self._json(200, base)

    def _flux(self, requete: dict) -> None:
        try:
            duree = float(requete.get("duree", [DUREE_FLUX])[0])
        except ValueError:
            duree = DUREE_FLUX
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        debut = time.monotonic()
        numero = 0
        while True:
            charge = json.dumps(
                {
                    "numero": numero,
                    "service": NOM,
                    "horodatage": round(time.time(), 3),
                }
            )
            try:
                self.wfile.write(f"data: {charge}\n\n".encode())
                self.wfile.flush()
            except OSError:
                return
            numero += 1
            prochain = debut + numero * BATTEMENT
            if prochain > debut + duree:
                break
            time.sleep(max(0.0, prochain - time.monotonic()))
        time.sleep(max(0.0, debut + duree - time.monotonic()))
        self.close_connection = True

    def log_message(self, *args) -> None:
        return


class Serveur(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128
    allow_reuse_address = True


if __name__ == "__main__":
    Serveur((BIND, PORT), Service).serve_forever()
