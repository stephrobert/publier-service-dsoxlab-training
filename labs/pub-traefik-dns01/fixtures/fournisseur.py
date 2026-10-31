#!/usr/bin/env python3
"""Fournisseur DNS de test du lab pub-traefik-dns01.

Il joue le rôle de l'API d'un hébergeur DNS, devant le serveur faisant
autorité `pebble-challtestsrv`, qui n'a lui-même aucune authentification.

Il parle le protocole `httpreq` de lego (mode par défaut), que Traefik sait
utiliser comme fournisseur DNS-01 :

  POST /present   {"fqdn": "_acme-challenge.<nom>.", "value": "<jeton>"}
  POST /cleanup   {"fqdn": "_acme-challenge.<nom>.", "value": "<jeton>"}

Chaque appel s'authentifie en Basic. Un COMPTE porte une liste de zones : il
ne peut poser ou retirer un TXT que sous `_acme-challenge.` d'un nom de ses
zones. Le compte `admin` a toutes les zones et peut créer des comptes :

  POST /comptes   {"nom": "<nom>", "zone": "<zone>"}   -> {"nom", "mdp", "zone"}
  GET  /comptes                                       -> [{"nom", "zones"}]

Chaque opération est journalisée, une ligne JSON par appel, dans JOURNAL :
c'est ce que lisent les tests, pas la configuration de l'apprenant.

Usage : fournisseur.py <comptes.json> <journal.jsonl> <url-challtestsrv>
"""

from __future__ import annotations

import base64
import json
import secrets
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COMPTES, JOURNAL, CHALLTESTSRV = sys.argv[1], sys.argv[2], sys.argv[3].rstrip("/")
PORT = 8060
VERROU = threading.Lock()


def charger() -> dict:
    with open(COMPTES, encoding="utf-8") as fichier:
        return json.load(fichier)


def enregistrer(comptes: dict) -> None:
    with open(COMPTES, "w", encoding="utf-8") as fichier:
        json.dump(comptes, fichier, indent=2)
        fichier.write("\n")


def journaliser(**champs) -> None:
    champs["t"] = round(time.time(), 3)
    with VERROU, open(JOURNAL, "a", encoding="utf-8") as fichier:
        fichier.write(json.dumps(champs) + "\n")


def autorise(zones: list[str], nom: str) -> bool:
    """Le nom (sans `_acme-challenge.`) est-il dans une des zones ?"""
    if "*" in zones:
        return True
    return any(nom == zone or nom.endswith("." + zone) for zone in zones)


def challtestsrv(chemin: str, corps: dict) -> None:
    requete = urllib.request.Request(
        CHALLTESTSRV + chemin,
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requete, timeout=5) as reponse:
        reponse.read()


class Fournisseur(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:  # le journal JSON suffit
        return

    def _repondre(self, statut: int, corps: object) -> None:
        donnees = json.dumps(corps).encode()
        self.send_response(statut)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def _compte(self) -> tuple[str, dict] | None:
        entete = self.headers.get("Authorization", "")
        if not entete.startswith("Basic "):
            return None
        try:
            nom, _, mdp = base64.b64decode(entete[6:]).decode().partition(":")
        except ValueError:
            return None
        compte = charger().get(nom)
        if compte is None or not secrets.compare_digest(compte["mdp"], mdp):
            return None
        return nom, compte

    def _corps(self) -> dict:
        longueur = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(longueur) or b"{}")
        except ValueError:
            return {}

    def do_GET(self) -> None:
        identite = self._compte()
        if identite is None:
            self._repondre(401, {"erreur": "authentification requise"})
            return
        nom, compte = identite
        if self.path != "/comptes" or "*" not in compte["zones"]:
            self._repondre(403, {"erreur": "réservé au compte admin"})
            return
        self._repondre(200, [{"nom": n, "zones": c["zones"]} for n, c in charger().items()])

    def do_POST(self) -> None:
        identite = self._compte()
        if identite is None:
            journaliser(compte=None, op=self.path, statut=401)
            self._repondre(401, {"erreur": "authentification requise"})
            return
        nom, compte = identite
        corps = self._corps()

        if self.path == "/comptes":
            if "*" not in compte["zones"]:
                self._repondre(403, {"erreur": "réservé au compte admin"})
                return
            nouveau, zone = str(corps.get("nom", "")), str(corps.get("zone", "")).strip(".").lower()
            if not nouveau or not zone or nouveau == "admin":
                self._repondre(400, {"erreur": "nom et zone requis"})
                return
            with VERROU:
                comptes = charger()
                if nouveau in comptes:
                    self._repondre(409, {"erreur": "compte existant"})
                    return
                mdp = secrets.token_urlsafe(18)
                comptes[nouveau] = {"mdp": mdp, "zones": [zone]}
                enregistrer(comptes)
            journaliser(compte=nom, op="/comptes", cree=nouveau, zone=zone, statut=201)
            self._repondre(201, {"nom": nouveau, "mdp": mdp, "zone": zone})
            return

        if self.path not in ("/present", "/cleanup"):
            self._repondre(404, {"erreur": "inconnu"})
            return
        fqdn = str(corps.get("fqdn", "")).strip(".").lower()
        prefixe = "_acme-challenge."
        cible = fqdn[len(prefixe):] if fqdn.startswith(prefixe) else None
        if cible is None or not autorise(compte["zones"], cible):
            journaliser(compte=nom, op=self.path, fqdn=fqdn, statut=403)
            self._repondre(403, {"erreur": f"{fqdn} hors des zones du compte {nom}"})
            return
        try:
            if self.path == "/present":
                challtestsrv("/set-txt", {"host": fqdn + ".", "value": str(corps.get("value", ""))})
            else:
                challtestsrv("/clear-txt", {"host": fqdn + "."})
        except OSError as erreur:
            journaliser(compte=nom, op=self.path, fqdn=fqdn, statut=502)
            self._repondre(502, {"erreur": f"serveur faisant autorité injoignable : {erreur}"})
            return
        journaliser(compte=nom, op=self.path, fqdn=fqdn, statut=200)
        self._repondre(200, {"ok": True})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Fournisseur).serve_forever()
