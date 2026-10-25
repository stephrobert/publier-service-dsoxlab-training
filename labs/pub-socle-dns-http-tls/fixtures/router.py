"""Routeur TLS minimal du lab pub-socle-dns-http-tls.

Reproduit, en plus petit, le comportement réel d'un reverse proxy TLS : le
SNI de la poignée de main choisit le certificat présenté, et l'en-tête HTTP
Host choisit ensuite l'application qui répond. Les deux décisions sont
indépendantes : un nom peut obtenir le bon certificat et atteindre, par le
jeu du Host, une tout autre application. C'est exactement le comportement
documenté de Nginx (le SNI ne sert qu'à choisir le bloc TLS, le Host choisit
le bloc HTTP), reproduit ici pour qu'il soit observable sans dépendre d'une
version particulière d'un reverse proxy externe.

La configuration vient de /etc/pub-dht/routes.yaml, relue à chaque
connexion : un changement de l'apprenant est donc pris en compte sans
redémarrage.
"""

from __future__ import annotations

import socket
import ssl
import threading

import yaml

CONFIG = "/etc/pub-dht/routes.yaml"
ADRESSE = ("0.0.0.0", 443)


def _charger_config() -> dict:
    with open(CONFIG, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)


def _contexte_pour(entree: dict) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(entree["cert"], entree["cle"])
    return ctx


def _choisir_certificat(sslsock, nom_demande, _ctx_initial):
    """Rappel SNI : exécuté par le module ssl pendant la poignée de main."""
    cfg = _charger_config()
    entree = cfg["noms"].get(nom_demande)
    if entree is None:
        if (cfg.get("inconnu") or {}).get("action") == "refuser":
            return ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
        # Repli implicite : le premier nom déclaré, comme un reverse proxy
        # sans bloc par défaut explicite retombe sur son premier bloc.
        entree = next(iter(cfg["noms"].values()))
    sslsock.context = _contexte_pour(entree)
    return None


def _lire_requete(sock: ssl.SSLSocket) -> bytes:
    tampon = b""
    sock.settimeout(5)
    while b"\r\n\r\n" not in tampon:
        morceau = sock.recv(4096)
        if not morceau:
            break
        tampon += morceau
    return tampon


def _hote_demande(requete: bytes) -> str:
    for ligne in requete.split(b"\r\n"):
        if ligne.lower().startswith(b"host:"):
            return ligne.split(b":", 1)[1].strip().decode().split(":")[0]
    return ""


def _repondre_refus(sock: ssl.SSLSocket) -> None:
    corps = b"Nom inconnu refuse.\n"
    sock.sendall(
        b"HTTP/1.0 421 Misdirected Request\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: " + str(len(corps)).encode() + b"\r\n\r\n" + corps
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
        hote = _hote_demande(requete)
        cfg = _charger_config()
        entree = cfg["noms"].get(hote)
        if entree is None:
            if (cfg.get("inconnu") or {}).get("action") == "refuser":
                _repondre_refus(sock)
                return
            entree = next(iter(cfg["noms"].values()))
        _relayer(sock, requete, entree["port_backend"])
    except (ssl.SSLError, OSError):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass


def principal() -> None:
    cfg = _charger_config()
    ctx = _contexte_pour(next(iter(cfg["noms"].values())))
    ctx.sni_callback = _choisir_certificat

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
