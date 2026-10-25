#!/usr/bin/env python3
"""Sondeur fourni pour le lab pub-socle-disponibilite : observe le
répartiteur et les backends depuis leur point de vue réel (une requête
HTTP par point d'entrée), au lieu de supposer ce que fait un produit
précis. Ce n'est pas un outil que l'apprenant écrit : c'est l'instrument
d'observation, déjà installé par `prepare.sh` sur edge.lab.

Usage ::

    python3 sonder.py echantillon <port_lb> <n>
    python3 sonder.py direct <port_backend>
    python3 sonder.py indisponible <port>

Chaque sous-commande imprime un objet JSON sur stdout.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request


def _get(port: str, chemin: str = "/echo") -> dict:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}{chemin}", timeout=2
        ) as reponse:
            return {"statut": reponse.status, "corps": json.loads(reponse.read())}
    except urllib.error.HTTPError as erreur:
        return {"statut": erreur.code, "corps": None}
    except (urllib.error.URLError, OSError) as erreur:
        return {"statut": None, "erreur": str(erreur)}


def _echantillon(port: str, n: str) -> dict:
    identites = []
    for _ in range(int(n)):
        sortie = _get(port)
        if sortie.get("corps"):
            identites.append(sortie["corps"].get("backend"))
        else:
            identites.append(None)
    return {"identites": identites}


def _direct(port: str) -> dict:
    return _get(port)


def _indisponible(port: str) -> dict:
    try:
        socket.create_connection(("127.0.0.1", int(port)), timeout=2).close()
        return {"joignable": True}
    except OSError as erreur:
        return {"joignable": False, "erreur": str(erreur)}


def principal() -> None:
    commande = sys.argv[1]
    if commande == "echantillon":
        sortie = _echantillon(sys.argv[2], sys.argv[3])
    elif commande == "direct":
        sortie = _direct(sys.argv[2])
    elif commande == "indisponible":
        sortie = _indisponible(sys.argv[2])
    else:
        raise SystemExit(f"commande inconnue: {commande}")
    print(json.dumps(sortie))


if __name__ == "__main__":
    principal()
