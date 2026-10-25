"""Routeur TLS du lab pub-socle-mise-en-service.

Termine TLS pour ``service.mes.test`` sur edge.lab et relaie vers l'une des
deux origines selon ``/etc/pub-mes/route.yaml``.

Deux comportements distincts, à dessein :

- ``expose_interne`` est relu À CHAQUE requête : une correction de la
  recette prend effet tout de suite, sans redémarrage.
- ``origine_active`` est au contraire mis en cache pendant
  ``ttl_cache_s`` secondes : un changement de fichier seul ne suffit pas à
  faire revenir le routeur sur l'ancienne origine avant l'expiration du
  cache. Poser le marqueur ``/var/lib/pub-mes/purge`` force une relecture
  immédiate puis s'efface de lui-même : c'est la bascule documentée que
  « rollback » attend, pas une simple attente passive.
"""

from __future__ import annotations

import os
import socket
import ssl
import threading
import time

import yaml

CONFIG = "/etc/pub-mes/route.yaml"
PURGE = "/var/lib/pub-mes/purge"
CERT = "/etc/pub-mes/certs/service.mes.test.crt"
CLE = "/etc/pub-mes/certs/service.mes.test.key"
ADRESSE = ("0.0.0.0", 443)

_VERROU = threading.Lock()
_CACHE_ORIGINE = {"valeur": None, "ts": 0.0}


def _charger_config() -> dict:
    with open(CONFIG, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier) or {}


def _origine_active(cfg: dict) -> str:
    ttl = max(0.0, float(cfg.get("ttl_cache_s", 0)))
    with _VERROU:
        maintenant = time.monotonic()
        perime = (maintenant - _CACHE_ORIGINE["ts"]) > ttl
        purger = os.path.exists(PURGE)
        if _CACHE_ORIGINE["valeur"] is None or perime or purger:
            _CACHE_ORIGINE["valeur"] = cfg.get("origine_active", "a")
            _CACHE_ORIGINE["ts"] = maintenant
            if purger:
                try:
                    os.remove(PURGE)
                except OSError:
                    pass
        return _CACHE_ORIGINE["valeur"]


def _port_pour(cfg: dict, origine: str) -> int:
    return int(cfg.get(f"port_{origine}"))


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
    with socket.create_connection(("127.0.0.1", port_backend), timeout=5) as amont:
        amont.sendall(requete)
        amont.settimeout(5)
        while True:
            morceau = amont.recv(4096)
            if not morceau:
                break
            sock.sendall(morceau)


def _traiter(sock: ssl.SSLSocket) -> None:
    try:
        requete = _lire_requete(sock)
        if not requete:
            return
        chemin = _chemin_demande(requete)
        cfg = _charger_config()
        if chemin.startswith("/interne/"):
            if cfg.get("expose_interne"):
                origine = _origine_active(cfg)
                _relayer(sock, requete, _port_pour(cfg, origine))
            else:
                _repondre(sock, 403, "Forbidden", b'{"erreur": "route interne refusee"}')
            return
        origine = _origine_active(cfg)
        _relayer(sock, requete, _port_pour(cfg, origine))
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
    brut.bind(ADRESSE)
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
