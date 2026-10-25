#!/usr/bin/env python3
"""API de commandes du lab : redirections, statuts et réponse perdue après écriture."""

import json
import os
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ["API_PORT"])
ETAT = os.environ["STATE_DIRECTORY"]
RECU = os.path.join(ETAT, "recu.jsonl")
ECRITURES = os.path.join(ETAT, "ecritures.jsonl")
CLES = os.path.join(ETAT, "cles.json")
verrou = threading.Lock()
perdues: set[str] = set()


def ajouter(chemin, objet):
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(objet) + "\n")


def lire_ecritures():
    try:
        with open(ECRITURES, encoding="utf-8") as f:
            return [json.loads(ligne) for ligne in f if ligne.strip()]
    except FileNotFoundError:
        return []


def lire_cles():
    try:
        with open(CLES, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _corps(self):
        longueur = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(longueur).decode("utf-8", "replace") if longueur else ""

    def _repondre(self, code, objet=None, entetes=None):
        donnees = json.dumps(objet).encode() if objet is not None else b""
        self.send_response(code)
        for nom, valeur in (entetes or {}).items():
            self.send_header(nom, valeur)
        if donnees:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def _journaliser(self, corps):
        with verrou:
            ajouter(RECU, {"methode": self.command, "chemin": self.path,
                           "entetes": {k.lower(): v for k, v in self.headers.items()},
                           "corps": corps})

    def _traiter(self):
        corps = self._corps()
        self._journaliser(corps)
        chemin = self.path.split("?")[0]
        parts = chemin.strip("/").split("/")
        if parts[0] == "redir" and len(parts) >= 3:
            self._repondre(int(parts[1]), None, {"Location": "/" + "/".join(parts[2:])})
        elif chemin == "/refus":
            self._repondre(403, {"error": "refus applicatif"})
        elif chemin == "/erreur":
            self._repondre(500, {"error": "erreur serveur"})
        elif chemin == "/commandes" and self.command == "POST":
            self._creer(corps)
        elif parts[0] == "commandes" and len(parts) == 2 and self.command == "GET":
            existe = any(e["ref"] == parts[1] for e in lire_ecritures())
            self._repondre(200 if existe else 404,
                           {"ref": parts[1]} if existe else {"error": "absente"})
        else:
            self._repondre(404, {"error": "absent"})

    def _creer(self, corps):
        try:
            donnees = json.loads(corps or "{}")
        except json.JSONDecodeError:
            self._repondre(400, {"error": "json invalide"})
            return
        ref = str(donnees.get("ref") or donnees.get("jeton") or uuid.uuid4())
        cle = self.headers.get("Idempotency-Key")
        with verrou:
            cles = lire_cles()
            if cle and cle in cles:
                reponse = cles[cle]
                rejeu = True
            else:
                ajouter(ECRITURES, {"ref": ref, "methode": self.command})
                reponse = {"ref": ref, "statut": "creee"}
                rejeu = False
                if cle:
                    cles[cle] = reponse
                    with open(CLES, "w", encoding="utf-8") as f:
                        json.dump(cles, f)
            perdre = ref.startswith("perdue-") and ref not in perdues and not rejeu
            if perdre:
                perdues.add(ref)
        if perdre:
            # L'écriture est faite, la réponse ne partira jamais.
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        self._repondre(200 if rejeu else 201, reponse)

    do_GET = do_POST = do_PUT = do_DELETE = _traiter

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
