#!/usr/bin/env python3
"""Les backends de pub-haproxy-flux-delais.

Un seul processus sert trois choses, et chacune existe pour rendre UNE
mesure possible :

  - deux instances HTTP identiques, A et B, chacune avec sa PROPRE memoire
    de sessions. Une session ouverte sur A est inconnue de B : c'est ce qui
    rend une politique de session mesurable, et c'est aussi ce qui en montre
    la limite, puisque coller un client a une instance n'est pas repliquer
    son etat ;

  - un point d'ecriture qui compte l'ecriture PUIS FERME LA CONNEXION SANS
    REPONDRE. Il simule la panne la plus traitre d'un proxy : la reponse
    perdue. Le travail a eu lieu, le client ne le sait pas, et un proxy qui
    reessaie le fait avoir lieu deux fois ;

  - un flux d'evenements dont le battement est LENT et horodate, et un
    WebSocket qui ne dit rien de lui-meme. Les deux mesurent la meme chose
    par deux chemins : une borne d'inactivite plus courte que le silence de
    l'application coupe un flux qui se portait bien.
"""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT_A = 18181
PORT_B = 18182
PORT_WS = 18183
BATTEMENT = 12
MAGIE_WS = "258EAFA5-E914-47DA-95CA-5AB0DC85B11D"


class Memoire:
    """L'etat d'une instance. Il ne sort pas d'elle, et c'est le sujet."""

    def __init__(self, nom: str) -> None:
        self.nom = nom
        self.verrou = threading.Lock()
        self.sessions: set[str] = set()
        self.ecritures = 0


def fabriquer(memoire: Memoire):
    class Service(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _rendre(self, statut, corps, entetes=None):
            self.send_response(statut)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            for nom, valeur in (entetes or {}).items():
                self.send_header(nom, valeur)
            self.end_headers()
            self.wfile.write(corps)

        def _jeton(self) -> str:
            brut = self.headers.get("Cookie", "")
            for morceau in brut.split(";"):
                morceau = morceau.strip()
                if morceau.startswith("JETON="):
                    return morceau[6:]
            return ""

        # -- lecture ------------------------------------------------------
        def do_GET(self):
            chemin = self.path.split("?", 1)[0]
            parametres = {}
            if "?" in self.path:
                for couple in self.path.split("?", 1)[1].split("&"):
                    if "=" in couple:
                        cle, valeur = couple.split("=", 1)
                        parametres[cle] = valeur

            if chemin == "/ecritures":
                with memoire.verrou:
                    compte = memoire.ecritures
                self._rendre(200, f"{compte}\n".encode())
                return

            if chemin == "/session/ouvrir":
                jeton = uuid.uuid4().hex
                with memoire.verrou:
                    memoire.sessions.add(jeton)
                self._rendre(
                    200,
                    f"session ouverte sur {memoire.nom}\n".encode(),
                    {"Set-Cookie": f"JETON={jeton}; Path=/"},
                )
                return

            if chemin == "/session/lire":
                jeton = self._jeton()
                with memoire.verrou:
                    connue = jeton in memoire.sessions
                if connue:
                    self._rendre(
                        200, f"session connue sur {memoire.nom}\n".encode()
                    )
                else:
                    # 409 et non 200 : une session perdue n'est pas une page
                    # qui manque, c'est un etat que le client croyait avoir.
                    self._rendre(
                        409, f"session inconnue sur {memoire.nom}\n".encode()
                    )
                return

            if chemin == "/lent":
                try:
                    duree = float(parametres.get("duree", "1"))
                except ValueError:
                    duree = 1.0
                time.sleep(duree)
                self._rendre(
                    200,
                    f"lent {duree}s sur {memoire.nom}\n".encode(),
                )
                return

            if chemin == "/sse":
                self._evenements(parametres)
                return

            self._rendre(
                200,
                f"pub-haproxy-flux-delais service {memoire.nom}\n"
                f"chemin: {self.path}\n".encode(),
            )

        # -- ecriture -----------------------------------------------------
        def do_POST(self):
            chemin = self.path.split("?", 1)[0]
            if chemin != "/ecrire":
                self._rendre(404, b"inconnu\n")
                return

            longueur = int(self.headers.get("Content-Length", "0") or 0)
            if longueur:
                self.rfile.read(longueur)

            # L'ECRITURE A LIEU D'ABORD. C'est tout le sujet : le travail est
            # fait, et le client ne le saura pas.
            with memoire.verrou:
                memoire.ecritures += 1

            # Puis la connexion se ferme SANS reponse. Un proxy qui reessaie
            # une requete non idempotente la fera donc executer deux fois,
            # et le compteur metier est le seul temoin.
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            self.close_connection = True

        # -- flux d'evenements --------------------------------------------
        def _evenements(self, parametres):
            try:
                duree = float(parametres.get("duree", "30"))
            except ValueError:
                duree = 30.0
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            debut = time.monotonic()
            numero = 0
            while time.monotonic() - debut < duree:
                charge = json.dumps(
                    {
                        "numero": numero,
                        "instance": memoire.nom,
                        "horodatage": round(time.time(), 3),
                    }
                )
                try:
                    self.wfile.write(f"data: {charge}\n\n".encode())
                    self.wfile.flush()
                except OSError:
                    return
                numero += 1
                # LE BATTEMENT EST LENT, et c'est delibere : c'est le silence
                # entre deux evenements qui met une borne d'inactivite a
                # l'epreuve. Un battement d'une seconde ne mesurerait rien.
                time.sleep(BATTEMENT)
            self.close_connection = True

        def log_message(self, *args):
            return

    return Service


# --------------------------------------------------------------------------
# WebSocket, sur PORT_WS. Il ne dit rien de lui-meme entre deux messages :
# c'est `timeout tunnel` qui decide combien de temps une conversation
# silencieuse survit, et aucun autre reglage ne le remplace.
# --------------------------------------------------------------------------
def _trame(charge: bytes) -> bytes:
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


def _session_ws(conn: socket.socket) -> None:
    try:
        requete = conn.recv(4096).decode("utf-8", "replace")
        cle = ""
        for ligne in requete.split("\r\n"):
            if ligne.lower().startswith("sec-websocket-key:"):
                cle = ligne.split(":", 1)[1].strip()
        if not cle:
            conn.close()
            return
        accepte = base64.b64encode(
            hashlib.sha1((cle + MAGIE_WS).encode()).digest()  # noqa: S324
        ).decode()
        conn.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accepte}\r\n\r\n"
            ).encode()
        )
        while True:
            recu = _lire_trame(conn)
            if recu is None:
                break
            conn.sendall(_trame(b"echo:" + recu))
    except OSError:
        pass
    finally:
        conn.close()


def servir_websocket() -> None:
    serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur.bind(("127.0.0.1", PORT_WS))
    serveur.listen(16)
    while True:
        conn, _ = serveur.accept()
        threading.Thread(target=_session_ws, args=(conn,), daemon=True).start()


def servir_http(nom: str, port: int) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), fabriquer(Memoire(nom))).serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--battement":
        print(BATTEMENT)
        sys.exit(0)
    threading.Thread(target=servir_websocket, daemon=True).start()
    threading.Thread(target=servir_http, args=("a", PORT_A), daemon=True).start()
    servir_http("b", PORT_B)
