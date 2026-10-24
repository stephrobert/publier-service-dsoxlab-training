"""Verify rate limiting, JSON access logs and a private stub_status."""

from __future__ import annotations

import json
import socket
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
IP_CIBLE = lab_host_ip(CIBLE)
URL = "http://app.lab.test"
RESOLUTION = "--resolve app.lab.test:80:127.0.0.1"
JOURNAL = "/opt/pub-nginx-observation/logs/access.log"
CHAMPS = ("time", "remote_addr", "request_uri", "status", "request_time")


def _edge():
    return lab_host(CIBLE)


@pytest.mark.garde_fou
def test_application_reste_publiee() -> None:
    result = _edge().run(
        f"curl --max-time 5 --silent --show-error {RESOLUTION} {URL}/health"
    )
    assert result.rc == 0 and "Nginx observation backend: /health" in result.stdout, message(
        en="Nginx must keep publishing the application on port 80.",
        fr="Nginx doit continuer à publier l'application sur le port 80.",
    )


def test_stub_status_repond_en_local() -> None:
    result = _edge().run(
        "curl --max-time 5 --silent --show-error http://127.0.0.1:8081/stub_status"
    )
    assert result.rc == 0 and "Active connections" in result.stdout, message(
        en="stub_status must answer on 127.0.0.1:8081.",
        fr="stub_status doit répondre sur 127.0.0.1:8081.",
    )


def test_stub_status_nest_pas_joignable_a_distance() -> None:
    try:
        with socket.create_connection((IP_CIBLE, 8081), timeout=2):
            ouvert = True
    except OSError:
        ouvert = False
    assert not ouvert, message(
        en="Port 8081 must not accept connections on the network address.",
        fr="Le port 8081 ne doit pas accepter de connexion sur l'adresse réseau.",
    )


def test_journal_est_au_format_json() -> None:
    edge = _edge()
    edge.run(f"curl --max-time 5 --silent --output /dev/null {RESOLUTION} {URL}/journal-lab")
    time.sleep(1)
    result = edge.run(f"tail -n 20 {JOURNAL}")
    lignes = [ligne for ligne in result.stdout.splitlines() if ligne.strip()]
    objets = []
    for ligne in lignes:
        try:
            objets.append(json.loads(ligne))
        except ValueError:
            continue
    valides = [o for o in objets if isinstance(o, dict) and all(c in o for c in CHAMPS)]
    trouve = any(o.get("request_uri") == "/journal-lab" for o in valides)
    assert result.rc == 0 and lignes and len(valides) == len(lignes) and trouve, message(
        en=f"Every line of {JOURNAL} must be a JSON object with {CHAMPS}, "
        "including the request that was just sent.",
        fr=f"Chaque ligne de {JOURNAL} doit être un objet JSON avec {CHAMPS}, "
        "y compris la requête qui vient d'être envoyée.",
    )


def test_rafale_limitee_puis_service_retabli() -> None:
    edge = _edge()
    rafale = edge.run(
        "seq 1 60 | xargs -P 30 -I{} curl --max-time 5 --silent --output /dev/null "
        f"--write-out '%{{http_code}}\\n' {RESOLUTION} {URL}/rafale"
    )
    codes = rafale.stdout.split()
    time.sleep(3)
    apres = edge.run(
        f"curl --max-time 5 --silent --output /dev/null --write-out '%{{http_code}}' "
        f"{RESOLUTION} {URL}/apres"
    )
    assert "429" in codes and apres.stdout.strip() == "200", message(
        en="A burst must receive some 429 responses, and a single request "
        "after a short pause must receive 200.",
        fr="Une rafale doit recevoir des réponses 429, et une requête isolée "
        "après une courte pause doit recevoir 200.",
    )
