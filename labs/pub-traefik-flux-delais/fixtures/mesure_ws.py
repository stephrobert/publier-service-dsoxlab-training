#!/usr/bin/env python3
"""Client de mesure fourni pour le lab pub-traefik-flux-delais : vérifie
qu'un WebSocket relayé par Traefik survit à une période d'inactivité avant
d'échanger un message, plutôt que de se contenter de lire une réponse
finale. Installé par `prepare.sh` sur edge.lab (bibliothèque `websockets`).

Usage ::

    python3 mesure_ws.py <host> <port> <chemin> <attente_avant_s>

Imprime un objet JSON sur stdout : {"echo": "...", "erreur": null} ou
{"echo": null, "erreur": "..."}.
"""

from __future__ import annotations

import asyncio
import json
import sys


async def _verifier(host: str, port: str, chemin: str, attente_avant_s: str) -> dict:
    import websockets

    url = f"ws://{host}:{port}{chemin}"
    try:
        async with websockets.connect(url) as ws:
            await asyncio.sleep(float(attente_avant_s))
            await ws.send("ping")
            reponse = await asyncio.wait_for(ws.recv(), timeout=5)
            return {"echo": reponse, "erreur": None}
    except Exception as erreur:  # noqa: BLE001 - rapporté tel quel au test
        return {"echo": None, "erreur": f"{type(erreur).__name__}: {erreur}"}


def principal() -> None:
    sortie = asyncio.run(_verifier(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
    print(json.dumps(sortie))


if __name__ == "__main__":
    principal()
