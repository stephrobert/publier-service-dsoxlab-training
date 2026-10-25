"""Répartiteur opaque et deux backends identiques, pour le lab
pub-socle-disponibilite.

ROLE=repartiteur  seul point joignable du client ; sonde les deux
                  backends selon la politique (intervalle, seuils) et ne
                  relaie qu'à ceux qu'il tient pour sains. C'est lui qui
                  décide, selon la politique, s'il alterne réellement
                  entre les backends sains ou s'il colle au premier
                  trouvé.
ROLE=backend      une instance identifiable (BACKEND_ID=a ou b) ; répond
                  sur /echo et /sante. Sa santé n'est pas décidée par
                  elle-même : un drapeau de fichier, posé par le test,
                  simule une panne applicative sans toucher au
                  répartiteur.

Les trois instances tournent sur edge.lab, en boucle locale : une vraie
topologie à deux points d'entrée n'est pas disponible dans ce lab, qui
représente honnêtement un répartiteur unique, avec son unique point de
panne assumé (point_a_tester "point_unique").
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["ROLE"]
BIND = "127.0.0.1"
PORT = int(os.environ["PORT"])
POLITIQUE = os.environ.get("POLITIQUE", "/etc/pub-disp/politique.yaml")
BACKEND_ID = os.environ.get("BACKEND_ID", "")
DRAPEAU_MALSAIN = os.environ.get("DRAPEAU_MALSAIN", "")
PORT_A = int(os.environ.get("PORT_A", "0"))
PORT_B = int(os.environ.get("PORT_B", "0"))


def _charger_politique() -> dict:
    import yaml

    try:
        with open(POLITIQUE, encoding="utf-8") as fichier:
            return yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return {}


def _repondre(gestionnaire: BaseHTTPRequestHandler, code: int, corps: bytes) -> None:
    gestionnaire.send_response(code)
    gestionnaire.send_header("Content-Type", "application/json")
    gestionnaire.send_header("Content-Length", str(len(corps)))
    gestionnaire.end_headers()
    gestionnaire.wfile.write(corps)


# -- ROLE=backend -------------------------------------------------------


class GestionnaireBackend(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith("/sante"):
            if os.path.exists(DRAPEAU_MALSAIN):
                _repondre(self, 503, json.dumps({"sain": False}).encode())
            else:
                _repondre(self, 200, json.dumps({"sain": True}).encode())
        else:
            _repondre(self, 200, json.dumps({"backend": BACKEND_ID}).encode())


# -- ROLE=repartiteur -----------------------------------------------------

_VERROU = threading.Lock()
_ETAT = {
    "a": {"sain": True, "echecs": 0, "succes": 0},
    "b": {"sain": True, "echecs": 0, "succes": 0},
}
_DERNIER = {"valeur": None}


def _sonder(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/sante", timeout=2) as reponse:
            return reponse.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _boucle_sondes() -> None:
    # Le battement de la boucle (TICK) est fixe et court, indépendant de
    # l'intervalle de sonde configuré : chaque backend n'est sondé que
    # lorsque son propre délai est écoulé (horodatage mur-à-mur). Si la
    # boucle dormait selon un intervalle_s périmé (par exemple 20s) au
    # moment où la politique passe à 1s, un battement fixe évite qu'un
    # changement de politique reste bloqué jusqu'à la fin de ce sommeil.
    TICK = 0.2
    ports = {"a": PORT_A, "b": PORT_B}
    dernier_sonde = {"a": 0.0, "b": 0.0}
    while True:
        politique = _charger_politique()
        probe = politique.get("probe") or {}
        intervalle = max(0.2, probe.get("intervalle_s", 20))
        echecs_seuil = max(1, probe.get("echecs_avant_retrait", 20))
        succes_seuil = max(1, probe.get("succes_avant_retour", 20))
        maintenant = time.monotonic()
        for backend_id, port in ports.items():
            if maintenant - dernier_sonde[backend_id] < intervalle:
                continue
            dernier_sonde[backend_id] = maintenant
            sain = _sonder(port)
            with _VERROU:
                etat = _ETAT[backend_id]
                if sain:
                    etat["echecs"] = 0
                    if not etat["sain"]:
                        etat["succes"] += 1
                        if etat["succes"] >= succes_seuil:
                            etat["sain"] = True
                            etat["succes"] = 0
                else:
                    etat["succes"] = 0
                    if etat["sain"]:
                        etat["echecs"] += 1
                        if etat["echecs"] >= echecs_seuil:
                            etat["sain"] = False
                            etat["echecs"] = 0
        time.sleep(TICK)


class GestionnaireRepartiteur(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def do_GET(self):
        politique = _charger_politique()
        actif = (politique.get("repartition") or {}).get("actif", False)
        ports = {"a": PORT_A, "b": PORT_B}
        with _VERROU:
            sains = sorted(bid for bid, etat in _ETAT.items() if etat["sain"])
        if not sains:
            _repondre(self, 503, json.dumps({"erreur": "aucun backend sain"}).encode())
            return
        if actif:
            # Alterne réellement parmi les backends actuellement sains.
            dernier = _DERNIER["valeur"]
            indice = (sains.index(dernier) + 1) % len(sains) if dernier in sains else 0
            cible = sains[indice]
        else:
            # Repli bogué : colle toujours au premier backend sain trouvé
            # dans l'ordre alphabétique, jamais à l'autre tant qu'il
            # répond lui aussi.
            cible = sains[0]
        _DERNIER["valeur"] = cible
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{ports[cible]}/echo", timeout=2
            ) as reponse:
                code, corps = reponse.status, reponse.read()
        except (urllib.error.URLError, OSError):
            code, corps = 502, json.dumps({"erreur": "backend injoignable"}).encode()
        _repondre(self, code, corps)


def principal() -> None:
    if ROLE == "backend":
        ThreadingHTTPServer((BIND, PORT), GestionnaireBackend).serve_forever()
    else:
        threading.Thread(target=_boucle_sondes, daemon=True).start()
        ThreadingHTTPServer((BIND, PORT), GestionnaireRepartiteur).serve_forever()


if __name__ == "__main__":
    principal()
