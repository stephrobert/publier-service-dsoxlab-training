"""Chaîne de deux proxys inverses et une application, pour le lab
pub-socle-reverse-proxy.

ROLE=perimetre  seul maillon joignable du client, termine TLS, relaie en
                HTTP clair vers le maillon interne. C'est lui qui décide,
                selon la politique, si l'origine qu'il transmet est celle
                qu'il observe réellement ou celle que le client prétend.
ROLE=interne    n'est jamais censé être joint directement par le client,
                relaie vers l'application. C'est lui qui décide, selon la
                politique, si l'identité qu'il transmet est la sienne ou
                celle que le maillon précédent prétend déjà porter.
ROLE=backend    l'application : elle ne décide rien, elle se contente de
                rapporter l'adresse et l'identité qu'elle a reçues, et sert
                une donnée réservée si l'identité reçue est "admin".

Les trois rôles tournent sur edge.lab : une vraie topologie à deux sites
n'est pas disponible dans ce lab, qui la représente honnêtement par trois
instances distinctes sur le même hôte.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["ROLE"]
BIND = os.environ.get("BIND", "127.0.0.1")
PORT = int(os.environ["PORT"])
POLITIQUE = os.environ.get("POLITIQUE", "/etc/pub-rp/politique.yaml")


def _charger_politique() -> dict:
    import yaml

    try:
        with open(POLITIQUE, encoding="utf-8") as fichier:
            return yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return {}


def _relayer(url: str, entetes: dict[str, str]) -> tuple[int, bytes]:
    requete = urllib.request.Request(url, headers=entetes)
    try:
        with urllib.request.urlopen(requete, timeout=3) as reponse:
            return reponse.status, reponse.read()
    except urllib.error.HTTPError as erreur:
        return erreur.code, erreur.read()


class Gestionnaire(BaseHTTPRequestHandler):
    # HTTP/1.0 : la connexion se ferme après chaque réponse, comme dans les
    # autres labs de cette série.
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def _repondre(self, code: int, corps: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if ROLE == "perimetre":
            self._perimetre()
        elif ROLE == "interne":
            self._interne()
        else:
            self._backend()

    def _perimetre(self) -> None:
        """Seul point en contact direct avec le client : décide l'origine."""
        politique = _charger_politique()
        adresse_reelle = self.client_address[0]
        xff_client = self.headers.get("X-Forwarded-For")
        if (politique.get("origine") or {}).get("forcer_perimetre"):
            # Le périmètre ne fait confiance qu'à ce qu'il observe lui-même.
            origine = adresse_reelle
        else:
            # Repli bogué : un client peut imposer sa propre origine.
            origine = xff_client if xff_client else adresse_reelle
        entetes = {"X-Forwarded-For": origine}
        if "X-User" in self.headers:
            # Le périmètre ne gère pas l'identité, il transmet tel quel.
            entetes["X-User"] = self.headers["X-User"]
        code, corps = _relayer(
            f"http://127.0.0.1:{os.environ['INTERNE_PORT']}/", entetes
        )
        self._repondre(code, corps)

    def _interne(self) -> None:
        """Jamais censé être joint par le client : décide l'identité."""
        politique = _charger_politique()
        entetes = {}
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            entetes["X-Forwarded-For"] = xff
        if (politique.get("identite") or {}).get("forcer_anonyme"):
            # L'interne impose sa propre décision, quoi que porte la requête.
            entetes["X-User"] = "anonyme"
        else:
            # Repli bogué : une identité déjà présente est reconduite.
            entetes["X-User"] = self.headers.get("X-User", "anonyme")
        code, corps = _relayer(
            f"http://127.0.0.1:{os.environ['BACKEND_PORT']}/", entetes
        )
        self._repondre(code, corps)

    def _backend(self) -> None:
        """Ne décide rien : rapporte ce qu'elle a reçu, sert si "admin"."""
        objet = {
            "ip_retenue": self.headers.get("X-Forwarded-For", ""),
            "identite_retenue": self.headers.get("X-User", ""),
        }
        if objet["identite_retenue"] == "admin":
            objet["secret"] = os.environ.get("SECRET", "")
        self._repondre(200, json.dumps(objet).encode())


def principal() -> None:
    serveur = ThreadingHTTPServer((BIND, PORT), Gestionnaire)
    if ROLE == "perimetre":
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexte.load_cert_chain(
            os.environ["TLS_CERT"], os.environ["TLS_KEY"]
        )
        serveur.socket = contexte.wrap_socket(serveur.socket, server_side=True)
    serveur.serve_forever()


if __name__ == "__main__":
    principal()
