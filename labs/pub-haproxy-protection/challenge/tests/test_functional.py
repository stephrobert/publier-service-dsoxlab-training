"""Verify the admin ACL, the security headers and the per-client rate limit."""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
IP_CIBLE = lab_host_ip(CIBLE)


def _edge():
    return lab_host(CIBLE)


def _code(edge, url: str) -> str:
    result = edge.run(
        f"curl --max-time 5 --silent --output /dev/null --write-out '%{{http_code}}' {url}"
    )
    return result.stdout.strip()


@pytest.mark.garde_fou
def test_application_reste_publiee() -> None:
    result = _edge().run("curl --max-time 5 --silent --show-error http://127.0.0.1:80/health")
    assert result.rc == 0 and "HAProxy protection backend: /health" in result.stdout, message(
        en="HAProxy must keep publishing the application on port 80.",
        fr="HAProxy doit continuer à publier l'application sur le port 80.",
    )


def test_entetes_de_securite_sont_presents() -> None:
    result = _edge().run(
        "curl --max-time 5 --silent --dump-header - --output /dev/null "
        "http://127.0.0.1:80/health"
    )
    entetes = result.stdout.lower()
    manquants = [
        h
        for h in ("x-content-type-options: nosniff", "x-frame-options: deny")
        if h not in entetes
    ]
    assert result.rc == 0 and not manquants, message(
        en=f"Required security headers are missing: {manquants}.",
        fr=f"En-têtes de sécurité manquants : {manquants}.",
    )


def test_admin_est_reserve_a_la_boucle_locale() -> None:
    edge = _edge()
    local = _code(edge, "http://127.0.0.1:80/admin")
    distant = _code(edge, f"http://{IP_CIBLE}:80/admin")
    assert local == "200" and distant == "403", message(
        en=f"/admin must answer 200 from 127.0.0.1 and 403 from {IP_CIBLE} "
        f"(got {local} and {distant}).",
        fr=f"/admin doit répondre 200 depuis 127.0.0.1 et 403 depuis {IP_CIBLE} "
        f"(obtenu {local} et {distant}).",
    )


def test_rafale_recoit_429() -> None:
    # Dernier test du fichier : la fenêtre de limitation bloque ensuite le client.
    edge = _edge()
    rafale = edge.run(
        "seq 1 60 | xargs -P 20 -I{} curl --max-time 5 --silent --output /dev/null "
        "--write-out '%{http_code}\\n' http://127.0.0.1:80/rafale"
    )
    codes = rafale.stdout.split()
    assert "429" in codes and "200" in codes, message(
        en="A burst above 20 requests in 10 seconds must receive 429, while the "
        "first requests are still served.",
        fr="Une rafale au-delà de 20 requêtes en 10 secondes doit recevoir 429, "
        "alors que les premières requêtes sont servies.",
    )
    time.sleep(1)
