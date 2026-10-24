"""Assess external HTTPS access, ACME renewal, isolation, and recovery."""

from __future__ import annotations

import re
import socket
import ssl
import time

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
IP_CIBLE = lab_host_ip(CIBLE)
AUTORITE = "/opt/pub-traefik-acme/pebble-root.pem"
MARQUEUR_SERIAL_INITIAL = (
    "/opt/pub-traefik-acme/assessment-initial-certificate-serial"
)
NOMS = ("app.lab.test", "docs.lab.test")
DELAI_EPREUVE_S = 60 * 60
DELAI_DEMARRAGE_S = 45
DELAI_RENOUVELLEMENT_S = 120


def _edge():
    return lab_host(CIBLE)


def _date_depart(edge) -> int:
    result = edge.run("cat /opt/pub-traefik-acme/assessment-started-at")
    assert result.rc == 0 and result.stdout.strip().isdigit(), message(
        en="The assessment timer is missing; restart the lab to begin the "
        "60-minute assessment.",
        fr="Le chronomètre est absent ; relancez le lab pour commencer "
        "l'épreuve de 60 minutes.",
    )
    return int(result.stdout.strip())


def _dans_le_delai(edge) -> bool:
    now = edge.run("date +%s")
    return now.rc == 0 and int(now.stdout.strip()) - _date_depart(edge) <= DELAI_EPREUVE_S


def _requete_https(nom: str, autorite: str) -> bytes:
    contexte = ssl.create_default_context(cadata=autorite)
    contexte.minimum_version = ssl.TLSVersion.TLSv1_2
    connexion = socket.create_connection((IP_CIBLE, 443), timeout=5)
    with contexte.wrap_socket(connexion, server_hostname=nom) as tls:
        tls.sendall(
            f"GET / HTTP/1.1\r\nHost: {nom}\r\nConnection: close\r\n\r\n".encode()
        )
        morceaux = []
        while morceau := tls.recv(4096):
            morceaux.append(morceau)
    return b"".join(morceaux)


def _reponse_externe(edge, nom: str) -> bytes | None:
    autorite = edge.run(f"cat {AUTORITE}")
    if autorite.rc != 0:
        return None
    try:
        with socket.create_connection((IP_CIBLE, 443), timeout=2):
            pass
    except OSError:
        return None
    fin = time.monotonic() + DELAI_DEMARRAGE_S
    while time.monotonic() < fin:
        try:
            return _requete_https(nom, autorite.stdout)
        except (OSError, ssl.SSLError):
            time.sleep(2)
    return None


def _serial_servi(edge, nom: str) -> str | None:
    result = edge.run(
        f"timeout 8 openssl s_client -connect 127.0.0.1:443 "
        f"-servername {nom} </dev/null 2>/dev/null | "
        "openssl x509 -noout -serial"
    )
    match = re.search(r"^serial=([0-9a-fA-F]+)$", result.stdout, re.M)
    return match.group(1).lower().lstrip("0") if result.rc == 0 and match else None


def _serials_emis(edge) -> list[str]:
    journal = edge.run("docker logs pub-renewal-pebble 2>&1")
    return [
        value.lower().lstrip("0")
        for value in re.findall(
            r"Issued certificate serial ([0-9a-fA-F]+)", journal.stdout
        )
    ]


def _ports_ouverts() -> list[int]:
    ouverts = []
    for port in (8080, 8081, 8082):
        try:
            with socket.create_connection((IP_CIBLE, port), timeout=2):
                ouverts.append(port)
        except OSError:
            continue
    return ouverts


def test_01_clients_externes_accedent_aux_services_sans_contourner_le_proxy() -> None:
    edge = _edge()
    reponses = {nom: _reponse_externe(edge, nom) for nom in NOMS}
    hote = {
        nom: re.search(rb"Hostname:\s*(\S+)", reponse).group(1)
        if reponse
        and re.search(rb"Hostname:\s*(\S+)", reponse)
        else None
        for nom, reponse in reponses.items()
    }
    ports = _ports_ouverts()
    assert (
        _dans_le_delai(edge)
        and all(
            reponses[nom] is not None
            and reponses[nom].startswith(b"HTTP/1.1 200")
            for nom in NOMS
        )
        and all(hote.values())
        and hote[NOMS[0]] != hote[NOMS[1]]
        and not ports
    ), message(
        en=f"External access must reach two distinct HTTPS backends while "
        f"ports 8080, 8081, and 8082 stay closed; open ports: {ports}.",
        fr=f"L'accès externe doit atteindre deux backends HTTPS distincts "
        f"tout en gardant les ports 8080, 8081 et 8082 fermés ; ports ouverts : "
        f"{ports}.",
    )


def test_02_certificat_renouvele_automatiquement_est_servi() -> None:
    edge = _edge()
    marqueur = edge.run(f"cat {MARQUEUR_SERIAL_INITIAL}")
    initial = (
        marqueur.stdout.strip()
        if marqueur.rc == 0
        else _serial_servi(edge, NOMS[0])
    )
    assert initial is not None, message(
        en="Traefik does not yet serve a certificate for app.lab.test.",
        fr="Traefik ne sert pas encore de certificat pour app.lab.test.",
    )
    if marqueur.rc != 0:
        sauvegarde = edge.run(
            f"printf '%s\\n' '{initial}' > {MARQUEUR_SERIAL_INITIAL}"
        )
        assert sauvegarde.rc == 0, message(
            en="Could not record the initial certificate serial for the "
            "renewal check.",
            fr="Impossible d'enregistrer le numéro du certificat initial "
            "pour vérifier le renouvellement.",
        )

    fin = time.monotonic() + DELAI_RENOUVELLEMENT_S
    servi = initial
    emis = _serials_emis(edge)
    while time.monotonic() < fin:
        reponse = _reponse_externe(edge, NOMS[0])
        servi = _serial_servi(edge, NOMS[0])
        emis = _serials_emis(edge)
        if (
            reponse
            and reponse.startswith(b"HTTP/1.1 200")
            and servi
            and servi != initial
            and servi in emis
        ):
            break
        time.sleep(5)

    assert (
        _dans_le_delai(edge)
        and         _dans_le_delai(edge)
        and
        servi is not None
        and servi != initial
        and servi in emis
    ), message(
        en=f"Pebble did not issue a renewed certificate served by Traefik "
        f"within {DELAI_RENOUVELLEMENT_S}s (initial={initial}, served={servi}, "
        f"issued={emis}).",
        fr=f"Pebble n'a pas émis de certificat renouvelé servi par Traefik "
        f"en {DELAI_RENOUVELLEMENT_S}s (initial={initial}, servi={servi}, "
        f"émis={emis}).",
    )


def test_03_les_services_reviennent_apres_redemarrage_de_docker() -> None:
    edge = _edge()
    avant = {nom: _reponse_externe(edge, nom) for nom in NOMS}
    assert all(
        reponse and reponse.startswith(b"HTTP/1.1 200")
        for reponse in avant.values()
    ), message(
        en="Both external HTTPS services must answer before restarting Docker.",
        fr="Les deux services HTTPS externes doivent répondre avant de "
        "redémarrer Docker.",
    )

    restart = edge.run("sudo systemctl restart docker")
    fin = time.monotonic() + 45
    apres = {}
    while time.monotonic() < fin:
        apres = {nom: _reponse_externe(edge, nom) for nom in NOMS}
        if all(
            reponse and reponse.startswith(b"HTTP/1.1 200")
            for reponse in apres.values()
        ):
            break
        time.sleep(3)
    assert (
        restart.rc == 0
        and _dans_le_delai(edge)
        and _dans_le_delai(edge)
        and all(
            reponse and reponse.startswith(b"HTTP/1.1 200")
            for reponse in apres.values()
        )
    ), message(
        en="Both HTTPS services must recover after the Docker daemon restarts.",
        fr="Les deux services HTTPS doivent revenir après le redémarrage du "
        "moteur Docker.",
    )
