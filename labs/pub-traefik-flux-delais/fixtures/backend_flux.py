"""Backend de flux pour le lab pub-traefik-flux-delais, point testé « flux »
(non critique) : un WebSocket et un flux SSE doivent réellement échanger
des données avant qu'un quelconque délai ne les ferme.

Deux serveurs tournent dans le même processus :

- un WebSocket d'écho sur le port WS_PORT (bibliothèque `websockets`) ;
- un flux SSE sur le port SSE_PORT (HTTP minimal fait main, comme dans le
  lab pub-socle-flux-longs) qui émet un événement numéroté chaque seconde,
  indéfiniment, tant que la connexion reste ouverte.

Ni l'un ni l'autre n'introduit de délai ou de coupure artificiels : si un
test les voit se fermer prématurément pendant une période d'inactivité,
la cause est forcément le réglage du point d'entrée Traefik en amont, pas
ce backend.
"""

from __future__ import annotations

import asyncio
import os

import websockets.asyncio.server as ws_server

WS_PORT = int(os.environ.get("WS_PORT", "8081"))
SSE_PORT = int(os.environ.get("SSE_PORT", "8080"))


async def _gerer_websocket(websocket) -> None:
    async for message in websocket:
        await websocket.send(f"echo:{message}")


async def _gerer_sse(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    ligne_requete = await reader.readline()
    while True:
        ligne = await reader.readline()
        if ligne in (b"\r\n", b""):
            break
    if b"/events" not in ligne_requete:
        writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return

    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/event-stream\r\n"
        b"Cache-Control: no-cache\r\n"
        b"Connection: keep-alive\r\n\r\n"
    )
    await writer.drain()

    compteur = 0
    try:
        while True:
            compteur += 1
            writer.write(f"data: evenement-{compteur}\n\n".encode())
            await writer.drain()
            await asyncio.sleep(1)
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def _principal() -> None:
    serveur_sse = await asyncio.start_server(_gerer_sse, "0.0.0.0", SSE_PORT)
    async with ws_server.serve(_gerer_websocket, "0.0.0.0", WS_PORT):
        async with serveur_sse:
            await serveur_sse.serve_forever()


if __name__ == "__main__":
    asyncio.run(_principal())
