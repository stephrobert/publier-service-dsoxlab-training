#!/usr/bin/env python3
"""Les trois backends du lab : WebSocket, SSE et gRPC, dans un seul processus.

POURQUOI gRPC SANS FICHIER .proto

grpcio accepte des gestionnaires GENERIQUES : une methode se declare par son
chemin, `/essai.Echo/Dire`, et recoit des octets bruts. Aucun protoc, aucun
code genere, et le test peut appeler la meme methode de la meme facon. Ce
lab porte sur le TRANSPORT, pas sur la serialisation.

LE WEBSOCKET EST ECRIT A LA MAIN

Le protocole tient en une poignee d'octets pour ce dont on a besoin : la
poignee de main HTTP, puis des trames texte non masquees cote serveur. Une
bibliotheque de plus serait une dependance de plus a installer sur la VM,
pour une fonction qu'on utilise trois fois.
"""

from __future__ import annotations

import base64
import hashlib
import socket
import struct
import threading
import time
from concurrent import futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import grpc

MAGIE_WS = "258EAFA5-E914-47DA-95CA-5AB0DC85B11D"


# --------------------------------------------------------------------------
# WebSocket, sur 18101
# --------------------------------------------------------------------------
def _trame(charge: bytes) -> bytes:
    """Une trame texte non masquee. Au-dela de 125 octets on n'ira pas."""
    return b"\x81" + bytes([len(charge)]) + charge


def _lire_trame(conn: socket.socket) -> bytes | None:
    entete = conn.recv(2)
    if len(entete) < 2:
        return None
    longueur = entete[1] & 0x7F
    masque = conn.recv(4) if entete[1] & 0x80 else b""
    charge = conn.recv(longueur)
    if masque:
        charge = bytes(o ^ masque[i % 4] for i, o in enumerate(charge))
    return charge


def servir_websocket() -> None:
    serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur.bind(("127.0.0.1", 18101))
    serveur.listen(16)
    while True:
        conn, _ = serveur.accept()
        threading.Thread(target=_session_ws, args=(conn,), daemon=True).start()


def _session_ws(conn: socket.socket) -> None:
    try:
        requete = conn.recv(4096).decode("utf-8", "replace")
        cle = ""
        upgrade = ""
        connexion = ""
        for ligne in requete.split("\r\n"):
            bas = ligne.lower()
            if bas.startswith("sec-websocket-key:"):
                cle = ligne.split(":", 1)[1].strip()
            elif bas.startswith("upgrade:"):
                upgrade = ligne.split(":", 1)[1].strip().lower()
            elif bas.startswith("connection:"):
                connexion = ligne.split(":", 1)[1].strip().lower()

        # LES TROIS EN-TETES, ET PAS SEULEMENT LA CLE. La RFC 6455 impose au
        # serveur de refuser une poignee de main sans `Upgrade: websocket`
        # ni `Connection: Upgrade`.
        #
        # Ce n'est pas du zele : `Upgrade` et `Connection` sont des en-tetes
        # DE SAUT, qu'un proxy retire s'il ne les repose pas explicitement,
        # alors que `Sec-WebSocket-Key` traverse sans rien demander. Un
        # backend qui se contente de la cle accepte donc la poignee que le
        # proxy MAL REGLE lui transmet, et le defaut que ce lab enseigne
        # disparait. Mesure du 2026-10-26 : le controle WebSocket passait
        # sur l'etat de depart, qui ne transmet pourtant ni l'un ni l'autre.
        if not cle or upgrade != "websocket" or "upgrade" not in connexion:
            conn.sendall(
                b"HTTP/1.1 400 Bad Request\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: 60\r\n\r\n"
                b"poignee refusee : Upgrade et Connection n'ont pas ete recus\n"
            )
            conn.close()
            return
        accepte = base64.b64encode(
            hashlib.sha1((cle + MAGIE_WS).encode()).digest()  # noqa: S324
        ).decode()
        conn.sendall(
            ("HTTP/1.1 101 Switching Protocols\r\n"
             "Upgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             f"Sec-WebSocket-Accept: {accepte}\r\n\r\n").encode()
        )
        # L'ECHANGE DANS LES DEUX SENS : on repond a ce qu'on recoit. Une
        # poignee de main reussie ne prouve rien si rien ne circule apres.
        while True:
            recu = _lire_trame(conn)
            if recu is None:
                break
            conn.sendall(_trame(b"echo:" + recu))
    except OSError:
        pass
    finally:
        conn.close()


# --------------------------------------------------------------------------
# SSE et HTTP ordinaire, sur 18102
# --------------------------------------------------------------------------
class Evenements(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/sse"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            # UN EVENEMENT PAR SECONDE : c'est ce rythme que la mise en
            # tampon detruit, en les livrant tous ensemble a la fin.
            for numero in range(1, 7):
                charge = f"data: evenement-{numero} t={time.time():.3f}\n\n"
                try:
                    self.wfile.write(charge.encode())
                    self.wfile.flush()
                except OSError:
                    return
                time.sleep(1)
            return
        corps = b"backend http ordinaire\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


# --------------------------------------------------------------------------
# gRPC, sur 18103
# --------------------------------------------------------------------------
def _dire(requete: bytes, contexte) -> bytes:
    """Une methode unaire. Un mot precis declenche une erreur APPLICATIVE."""
    if b"erreur" in requete:
        contexte.abort(grpc.StatusCode.INVALID_ARGUMENT, "argument refuse")
    return b"echo:" + requete


class Generique(grpc.GenericRpcHandler):
    def service(self, details):
        if details.method == "/essai.Echo/Dire":
            return grpc.unary_unary_rpc_method_handler(
                _dire,
                request_deserializer=lambda o: o,
                response_serializer=lambda o: o,
            )
        return None


def servir_grpc() -> None:
    serveur = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    serveur.add_generic_rpc_handlers((Generique(),))
    serveur.add_insecure_port("127.0.0.1:18103")
    serveur.start()
    serveur.wait_for_termination()


if __name__ == "__main__":
    threading.Thread(target=servir_websocket, daemon=True).start()
    threading.Thread(target=servir_grpc, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", 18102), Evenements).serve_forever()
