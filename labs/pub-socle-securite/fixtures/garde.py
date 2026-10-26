#!/usr/bin/env python3
"""Le banc parametrable du lab pub-socle-securite.

CE QU'IL EST, ET POURQUOI IL EXISTE

Le socle ne depend d'aucun reverse proxy particulier : ce qui s'y apprend est
d'ecrire une POLITIQUE, pas la syntaxe d'un outil. Ce garde lit donc
`politique.yaml` a chaque requete et applique ce qu'il y trouve. L'apprenant
ecrit la politique ; le garde ne fait que l'appliquer, fidelement, y compris
quand elle est trop permissive.

CE QU'IL NE FAIT PAS, ET C'EST LE SUJET DU LAB

Il ne corrige rien, il n'a aucune valeur par defaut sure, et il ne devine
aucune intention. Une politique vide laisse tout passer. Une politique qui
fait confiance a tout le monde fait confiance a tout le monde.

TROIS CLES, ET LA TROISIEME EST CELLE QU'ON OUBLIE

  routes             : quelle identite est exigee sur quel prefixe
  proxys_de_confiance: de quelles adresses un en-tete d'identite est cru
  journal            : quels champs sont EFFACES avant d'ecrire

Un journal qui conserve le `Authorization` d'une requete conserve un secret
en clair sur le disque, pour aussi longtemps que le journal vit. C'est le
point que la validation cherche avec une valeur sentinelle.
"""

from __future__ import annotations

import http.server
import json
import os
import pathlib
import urllib.request

import yaml

POLITIQUE = pathlib.Path("/opt/pub-socle-securite/politique.yaml")
JOURNAL = pathlib.Path("/opt/pub-socle-securite/acces.log")
DOSSIER = pathlib.Path("/opt/pub-socle-securite/dossier.json")
AMONT = "http://127.0.0.1:18090"

# Les identites du banc. Le jeton est l'identifiant ; il n'y a pas de mot de
# passe, ce lab porte sur la POLITIQUE et non sur l'authentification.
IDENTITES = {
    "jeton-utilisateur-7f3a": "utilisateur",
    "jeton-admin-91c4": "admin",
}


def _lire_politique() -> dict:
    """Relit la politique a chaque requete, pour que l'apprenant la voie agir.

    POURQUOI `yaml.safe_load` ET NON UN ANALYSEUR MAISON. Un analyseur ecrit
    pour l'occasion relit mal une politique pourtant valide, et l'apprenant
    cherche alors l'erreur chez lui. Le banc doit appliquer ce qui est ecrit,
    pas une approximation de ce qui est ecrit.

    Un fichier absent, vide ou illisible ne vaut pas « tout refuser » : il
    vaut une politique VIDE, donc tout autorise. C'est brutal, et c'est
    voulu : une politique qu'on croit posee et qui ne l'est pas doit se voir
    tout de suite, au lieu de se deguiser en securite.
    """
    if not POLITIQUE.is_file():
        return {}
    try:
        charge = yaml.safe_load(POLITIQUE.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return charge if isinstance(charge, dict) else {}


class Garde(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        politique = _lire_politique()
        identite = self._identite(politique)
        exigee = self._identite_exigee(politique)

        if exigee and identite != exigee and not (exigee == "utilisateur"
                                                  and identite == "admin"):
            self._refuser(401 if identite == "anonyme" else 403, identite)
            self._journaliser(politique, 401 if identite == "anonyme" else 403,
                              identite)
            return

        try:
            with urllib.request.urlopen(AMONT + self.path, timeout=5) as rep:
                corps = rep.read()
                statut = rep.status
        except OSError as erreur:
            corps = f"amont injoignable : {erreur}\n".encode()
            statut = 502

        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)
        self._journaliser(politique, statut, identite)

    def _identite(self, politique: dict) -> str:
        """Qui parle, selon la politique.

        LE POINT QUI DECIDE DU LAB. Un en-tete `X-Identite` n'est cru que si
        l'appelant figure dans `proxys_de_confiance`. Sans cette liste, tout
        appelant choisit son identite, et la politique ne protege rien.
        """
        confiance = politique.get("proxys_de_confiance") or []
        if isinstance(confiance, dict):
            confiance = list(confiance)
        annonce = self.headers.get("X-Identite", "")
        if annonce and self.client_address[0] in confiance:
            return annonce
        jeton = (self.headers.get("Authorization", "")
                 .removeprefix("Bearer ").strip())
        return IDENTITES.get(jeton, "anonyme")

    def _identite_exigee(self, politique: dict) -> str:
        routes = politique.get("routes") or {}
        if not isinstance(routes, dict):
            return ""
        meilleure, exigee = -1, ""
        for prefixe, role in routes.items():
            if self.path.startswith(prefixe) and len(prefixe) > meilleure:
                meilleure, exigee = len(prefixe), str(role)
        return "" if exigee in ("anonyme", "public") else exigee

    def _refuser(self, code: int, identite: str) -> None:
        corps = f"refus ({code}) pour l'identite {identite}\n".encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _journaliser(self, politique: dict, statut: int, identite: str) -> None:
        journal = politique.get("journal") or {}
        a_effacer = journal.get("effacer") if isinstance(journal, dict) else []
        if isinstance(a_effacer, dict):
            a_effacer = list(a_effacer)
        a_effacer = [str(c).lower() for c in (a_effacer or [])]

        entetes = {}
        for nom, valeur in self.headers.items():
            entetes[nom] = "[efface]" if nom.lower() in a_effacer else valeur

        ligne = {
            "chemin": self.path,
            "statut": statut,
            "identite": identite,
            "source": self.client_address[0],
            "entetes": entetes,
        }
        with JOURNAL.open("a", encoding="utf-8") as fichier:
            fichier.write(json.dumps(ligne, ensure_ascii=False) + "\n")

        # Le « dossier » est le resume que l'exploitant relit : il herite des
        # memes effacements, parce qu'un secret recopie ailleurs reste un
        # secret en clair.
        resume = {"dernier_chemin": self.path, "dernier_statut": statut,
                  "entetes": entetes}
        DOSSIER.write_text(json.dumps(resume, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    def log_message(self, *args):
        return


if __name__ == "__main__":
    for chemin in (JOURNAL, DOSSIER):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.touch(exist_ok=True)
        os.chmod(chemin, 0o644)
    http.server.ThreadingHTTPServer(("0.0.0.0", 80), Garde).serve_forever()
