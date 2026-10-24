"""Check private HAProxy metrics and their collection by Prometheus."""

from __future__ import annotations

import json
import socket
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
IP_CIBLE = lab_host_ip(CIBLE)


def _edge():
    return lab_host(CIBLE)


def _targets(edge) -> dict | None:
    result = edge.run(
        "curl --max-time 5 --silent --show-error "
        "http://127.0.0.1:9090/api/v1/targets"
    )
    return json.loads(result.stdout) if result.rc == 0 else None


@pytest.mark.garde_fou
def test_service_public_reste_accessible() -> None:
    result = _edge().run(
        "curl --max-time 5 --silent --show-error "
        "http://127.0.0.1:80/health"
    )
    assert result.rc == 0 and "HAProxy backend: /health" in result.stdout, message(
        en="The public HAProxy frontend must continue to serve its backend.",
        fr="Le frontend public HAProxy doit continuer à publier son backend.",
    )


def test_exporteur_fournit_les_metriques_de_sante() -> None:
    result = _edge().run(
        "curl --max-time 5 --silent --show-error "
        "http://127.0.0.1:8404/metrics"
    )
    assert (
        result.rc == 0
        and "haproxy_frontend_status" in result.stdout
        and "haproxy_server_status" in result.stdout
    ), message(
        en="The loopback-only /metrics endpoint must expose HAProxy frontend "
        "and backend health metrics.",
        fr="Le point /metrics, limité à la boucle locale, doit exposer les "
        "métriques de santé du frontend et du backend HAProxy.",
    )


def test_prometheus_collecte_une_cible_healthy() -> None:
    edge = _edge()
    echeance = time.monotonic() + 35
    cible_active = False
    while time.monotonic() < echeance:
        payload = _targets(edge)
        if payload is not None:
            cibles = payload.get("data", {}).get("activeTargets", [])
            cible = next(
                (item for item in cibles if item.get("labels", {}).get("job") == "haproxy"),
                None,
            )
            if cible and cible.get("health") == "up":
                cible_active = True
                break
        time.sleep(2)
    assert cible_active, message(
        en="Prometheus must report its HAProxy scrape target as up.",
        fr="Prometheus doit indiquer que sa cible de collecte HAProxy est active.",
    )


def test_exporteur_et_console_prometheus_ne_sont_pas_exposes() -> None:
    ouverts = []
    for port in (8404, 9090):
        try:
            with socket.create_connection((IP_CIBLE, port), timeout=2):
                ouverts.append(port)
        except OSError:
            continue
    assert not ouverts, message(
        en=f"Metrics and Prometheus UI ports must not accept remote connections "
        f"(reachable: {ouverts}).",
        fr=f"Les ports des métriques et de l'interface Prometheus ne doivent "
        f"pas accepter de connexion distante (joignables : {ouverts}).",
    )
