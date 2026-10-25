"""Routeur TLS du lab pub-epreuve-socle.

Termine TLS pour ``epreuve.test`` sur edge.lab et relaie vers le backend sur
``127.0.0.1:<port>`` lu dans ``/etc/pub-eps/route.yaml``.

Deux réglages viennent de l'environnement, posés une fois par
``prepare.sh`` et jamais changés en cours de route :

``BIND``   l'adresse d'écoute (``0.0.0.0`` normalement, ``127.0.0.1`` si
           l'incident touche le transport : le routeur tourne, mais seul
           edge.lab peut lui parler).
``CERT``/``CLE``  le certificat et la clé servis. Pointer ces variables sur
           un certificat qui n'est pas signé par l'autorité de test est
           l'incident « tls ».

Le port du backend, lui, vient de ``/etc/pub-eps/route.yaml`` et est relu à
chaque requête : un incident « route » (mauvais port dans ce fichier) ne se
corrige pas par un redémarrage du routeur, juste par la correction du
fichier.
"""

from __future__ import annotations

import os
import socket
import ssl
import threading

import yaml

CONFIG = "/etc/pub-eps/route.yaml"
CERT = os.environ.get("CERT", "/etc/pub-eps/certs/epreuve.test.crt")
CLE = os.environ.get("CLE", "/etc/pub-eps/certs/epreuve.test.key")
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "443"))


def _charger_config() -> dict:
    with open(CONFIG, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier) or {}


def _lire_requete(sock: ssl.SSLSocket) -> bytes:
    tampon = b""
    sock.settimeout(5)
    while b"\r\n\r\n" not in tampon:
        morceau = sock.recv(4096)
        if not morceau:
            break
        tampon += morceau
    return tampon


def _chemin_demande(requete: bytes) -> str:
    premiere_ligne = requete.split(b"\r\n", 1)[0]
    morceaux = premiere_ligne.split(b" ")
    return morceaux[1].decode() if len(morceaux) >= 2 else "/"


def _repondre(sock: ssl.SSLSocket, code: int, texte: str, corps: bytes) -> None:
    sock.sendall(
        f"HTTP/1.0 {code} {texte}\r\n".encode()
        + b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(corps)}\r\n\r\n".encode()
        + corps
    )


def _relayer(sock: ssl.SSLSocket, requete: bytes, port_backend: int) -> None:
    try:
        with socket.create_connection(("127.0.0.1", port_backend), timeout=5) as amont:
            amont.sendall(requete)
            amont.settimeout(5)
            while True:
                morceau = amont.recv(4096)
                if not morceau:
                    break
                sock.sendall(morceau)
    except OSError:
        _repondre(sock, 502, "Bad Gateway", b'{"erreur": "amont indisponible"}')


def _traiter(sock: ssl.SSLSocket) -> None:
    try:
        requete = _lire_requete(sock)
        if not requete:
            return
        chemin = _chemin_demande(requete)
        cfg = _charger_config()
        port_backend = int(cfg.get("port_backend", 0))
        if not port_backend:
            _repondre(sock, 502, "Bad Gateway", b'{"erreur": "route non configuree"}')
            return
        del chemin  # le routeur relaie tout, le backend tranche par route.
        _relayer(sock, requete, port_backend)
    except (ssl.SSLError, OSError, KeyError, ValueError):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass


def principal() -> None:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, CLE)

    brut = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    brut.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    brut.bind((BIND, PORT))
    brut.listen(64)
    while True:
        client, _ = brut.accept()
        try:
            tls = ctx.wrap_socket(client, server_side=True)
        except ssl.SSLError:
            continue
        threading.Thread(target=_traiter, args=(tls,), daemon=True).start()


if __name__ == "__main__":
    principal()
