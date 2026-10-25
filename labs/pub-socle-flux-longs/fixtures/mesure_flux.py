#!/usr/bin/env python3
"""Client de mesure fourni pour le lab pub-socle-flux-longs.

Ceci n'est pas un outil que l'apprenant écrit ou corrige : c'est
l'instrument d'observation, déjà installé par `prepare.sh` sur edge.lab,
qui mesure le handshake, l'aller-retour et la fermeture d'un WebSocket, et
observe l'instant d'arrivée de chaque ligne d'un flux SSE (données,
heartbeats, signal de panne), pas seulement le corps final de la réponse.

Usage ::

    python3 mesure_flux.py websocket <port_ws>
    python3 mesure_flux.py sse <port_sse> <duree_s>
    python3 mesure_flux.py panne <port_sse> <attente_avant_s> <attente_apres_s>

Chaque sous-commande imprime un objet JSON sur stdout.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time


async def _websocket(port: str) -> dict:
    import websockets

    t0 = time.monotonic()
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
        t_handshake = time.monotonic()
        t_envoi = time.monotonic()
        await ws.send("ping")
        reponse = await asyncio.wait_for(ws.recv(), timeout=10)
        t_reponse = time.monotonic()
        await ws.close()
        t_fermeture = time.monotonic()
    return {
        "handshake_ms": round((t_handshake - t0) * 1000, 1),
        "aller_retour_ms": round((t_reponse - t_envoi) * 1000, 1),
        "reponse": reponse,
        "fermeture_ms": round((t_fermeture - t_reponse) * 1000, 1),
    }


async def _lire_sse(port: str, duree_s: float) -> list[dict]:
    reader, writer = await asyncio.open_connection("127.0.0.1", int(port))
    writer.write(
        b"GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n"
    )
    await writer.drain()
    # Consommer les en-têtes de réponse.
    while True:
        ligne = await reader.readline()
        if ligne in (b"\r\n", b""):
            break

    evenements = []
    t0 = time.monotonic()
    tampon_ligne = b""
    try:
        while time.monotonic() - t0 < duree_s:
            reste = duree_s - (time.monotonic() - t0)
            if reste <= 0:
                break
            try:
                tampon_ligne = await asyncio.wait_for(reader.readline(), timeout=reste)
            except asyncio.TimeoutError:
                break
            if not tampon_ligne:
                evenements.append({"type": "fermeture", "t": round(time.monotonic() - t0, 3)})
                break
            texte = tampon_ligne.decode().rstrip("\n")
            instant = round(time.monotonic() - t0, 3)
            if texte.startswith(": heartbeat"):
                evenements.append({"type": "heartbeat", "t": instant})
            elif texte.startswith("event: panne"):
                evenements.append({"type": "panne", "t": instant})
            elif texte.startswith("data:"):
                evenements.append({"type": "donnee", "t": instant, "contenu": texte[5:].strip()})
    finally:
        writer.close()
    return evenements


async def _sse(port: str, duree_s: str) -> dict:
    evenements = await _lire_sse(port, float(duree_s))
    return {"evenements": evenements}


async def _panne(port: str, attente_avant_s: str, attente_apres_s: str) -> dict:
    reader, writer = await asyncio.open_connection("127.0.0.1", int(port))
    writer.write(
        b"GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n"
    )
    await writer.drain()
    while True:
        ligne = await reader.readline()
        if ligne in (b"\r\n", b""):
            break

    await asyncio.sleep(float(attente_avant_s))
    subprocess.run(
        ["sudo", "systemctl", "stop", "pub-flux-producteur.service"],
        check=True,
        capture_output=True,
    )

    evenements = []
    t0 = time.monotonic()
    duree = float(attente_apres_s)
    try:
        while time.monotonic() - t0 < duree:
            reste = duree - (time.monotonic() - t0)
            if reste <= 0:
                break
            try:
                ligne = await asyncio.wait_for(reader.readline(), timeout=reste)
            except asyncio.TimeoutError:
                break
            if not ligne:
                evenements.append({"type": "fermeture", "t": round(time.monotonic() - t0, 3)})
                break
            texte = ligne.decode().rstrip("\n")
            instant = round(time.monotonic() - t0, 3)
            if texte.startswith("event: panne"):
                evenements.append({"type": "panne", "t": instant})
            elif texte.startswith(": heartbeat"):
                evenements.append({"type": "heartbeat", "t": instant})
            elif texte.startswith("data:"):
                evenements.append({"type": "donnee", "t": instant})
    finally:
        writer.close()
    return {"evenements": evenements}


def principal() -> None:
    commande = sys.argv[1]
    if commande == "websocket":
        sortie = asyncio.run(_websocket(sys.argv[2]))
    elif commande == "sse":
        sortie = asyncio.run(_sse(sys.argv[2], sys.argv[3]))
    elif commande == "panne":
        sortie = asyncio.run(_panne(sys.argv[2], sys.argv[3], sys.argv[4]))
    else:
        raise SystemExit(f"commande inconnue: {commande}")
    print(json.dumps(sortie))


if __name__ == "__main__":
    principal()
