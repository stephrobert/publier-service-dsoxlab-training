"""Service de notifications (WebSocket + SSE) et producteur, pour le lab
pub-socle-flux-longs.

ROLE=producteur  émet une ligne de notification toutes les secondes sur
                 une connexion TCP en boucle locale. Son seul rôle est
                 d'exister ou de s'arrêter : le service ne décide rien à
                 sa place.
ROLE=service     expose un WebSocket (écho, avec un délai paramétrable)
                 et un flux SSE (relais des notifications du producteur,
                 avec une taille de tampon, un intervalle de heartbeat et
                 une politique de signalement de panne, tous les trois
                 paramétrables). Lit la même politique que les autres
                 labs de cette série, relue au démarrage de chaque
                 connexion (le flux déjà ouvert garde son réglage pour sa
                 propre durée de vie).

Les deux rôles tournent sur edge.lab, en boucle locale (127.0.0.1) : le
client de mesure fourni s'exécute sur ce même hôte.
"""

from __future__ import annotations

import asyncio
import os

import websockets.asyncio.server as ws_server

ROLE = os.environ["ROLE"]
POLITIQUE = os.environ.get("POLITIQUE", "/etc/pub-flux/politique.yaml")
PRODUCTEUR_PORT = int(os.environ.get("PRODUCTEUR_PORT", "0"))
WS_PORT = int(os.environ.get("WS_PORT", "0"))
SSE_PORT = int(os.environ.get("SSE_PORT", "0"))

_PANNE = object()


def _charger_politique() -> dict:
    import yaml

    try:
        with open(POLITIQUE, encoding="utf-8") as fichier:
            return yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return {}


# -- ROLE=producteur ---------------------------------------------------------


async def _producteur() -> None:
    async def gerer(reader, writer) -> None:
        compteur = 0
        try:
            while True:
                compteur += 1
                writer.write(
                    f"notification {compteur} {asyncio.get_event_loop().time():.3f}\n".encode()
                )
                await writer.drain()
                await asyncio.sleep(1)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    serveur = await asyncio.start_server(gerer, "127.0.0.1", PRODUCTEUR_PORT)
    async with serveur:
        await serveur.serve_forever()


# -- ROLE=service : WebSocket ------------------------------------------------


async def _gerer_websocket(websocket) -> None:
    async for message in websocket:
        politique = _charger_politique()
        delai_ms = (politique.get("websocket") or {}).get("delai_echo_ms", 0)
        await asyncio.sleep(delai_ms / 1000)
        await websocket.send(f"echo:{message}")


# -- ROLE=service : SSE -------------------------------------------------------

_ABONNES: list[asyncio.Queue] = []


async def _lire_producteur() -> None:
    # Boucle de reconnexion : une panne du producteur se signale aux
    # abonnés déjà ouverts, mais ne doit jamais arrêter définitivement la
    # lecture, sans quoi les connexions SSE ouvertes après coup (ou après
    # le retour du producteur) ne recevraient plus jamais rien.
    while True:
        try:
            reader, _writer = await asyncio.open_connection(
                "127.0.0.1", PRODUCTEUR_PORT
            )
        except (ConnectionRefusedError, OSError):
            await _signaler_panne()
            await asyncio.sleep(1)
            continue
        while True:
            ligne = await reader.readline()
            if not ligne:
                await _signaler_panne()
                break
            texte = ligne.decode().strip()
            for file_attente in list(_ABONNES):
                await file_attente.put(texte)
        await asyncio.sleep(1)


async def _signaler_panne() -> None:
    politique = _charger_politique()
    if (politique.get("panne") or {}).get("fermer_proprement"):
        for file_attente in list(_ABONNES):
            await file_attente.put(_PANNE)
    # Repli bogué : aucun signal, aucune fermeture. Les abonnés restent en
    # attente indéfiniment, sans jamais savoir pourquoi plus rien n'arrive.


async def _gerer_sse(reader, writer) -> None:
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

    file_attente: asyncio.Queue = asyncio.Queue()
    _ABONNES.append(file_attente)
    tampon: list[str] = []
    # Le heartbeat suit sa propre horloge murale, indépendante de l'arrivée
    # des notifications : avec `wait_for(..., timeout=intervalle)` seul, une
    # notification qui arrive plus vite que l'intervalle réinitialiserait
    # sans cesse le délai, et le heartbeat ne se déclencherait jamais tant
    # que le producteur reste actif, le vidant de son sens.
    dernier_heartbeat = asyncio.get_event_loop().time()
    try:
        while True:
            politique = _charger_politique()
            intervalle = (politique.get("inactivite") or {}).get(
                "intervalle_heartbeat_s", 2
            )
            taille_tampon = max(1, (politique.get("sse") or {}).get("taille_tampon", 1))
            reste = intervalle - (asyncio.get_event_loop().time() - dernier_heartbeat)
            if reste <= 0:
                writer.write(b": heartbeat\n\n")
                await writer.drain()
                dernier_heartbeat = asyncio.get_event_loop().time()
                continue
            try:
                item = await asyncio.wait_for(file_attente.get(), timeout=reste)
            except asyncio.TimeoutError:
                continue
            if item is _PANNE:
                writer.write(b"event: panne\ndata: producteur indisponible\n\n")
                await writer.drain()
                break
            tampon.append(item)
            if len(tampon) >= taille_tampon:
                for ligne_evt in tampon:
                    writer.write(f"data: {ligne_evt}\n\n".encode())
                await writer.drain()
                tampon.clear()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        _ABONNES.remove(file_attente)
        writer.close()


async def _service() -> None:
    serveur_sse = await asyncio.start_server(_gerer_sse, "127.0.0.1", SSE_PORT)
    async with ws_server.serve(_gerer_websocket, "127.0.0.1", WS_PORT):
        async with serveur_sse:
            await asyncio.gather(serveur_sse.serve_forever(), _lire_producteur())


def principal() -> None:
    if ROLE == "producteur":
        asyncio.run(_producteur())
    else:
        asyncio.run(_service())


if __name__ == "__main__":
    principal()
