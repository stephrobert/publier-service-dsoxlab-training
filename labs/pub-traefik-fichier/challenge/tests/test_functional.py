"""Verify file-provider routing and hot reload without restarting Traefik."""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
HOTE = "systemd.lab.test"
WORK = "/opt/pub-fichier"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _route(edge):
    return edge.run(
        "for _ in $(seq 1 20); do "
        "code=$(curl --max-time 2 --silent --show-error --output "
        f"{WORK}/response.txt --write-out '%{{http_code}}' "
        f"-H 'Host: {HOTE}' http://127.0.0.1/ || true); "
        "if [ \"$code\" = 200 ]; then cat "
        f"{WORK}/response.txt; printf '\\nHTTP=%s\\n' \"$code\"; exit 0; fi; "
        "sleep 1; done; printf 'HTTP=%s\\n' \"${code:-none}\"; exit 1"
    )


@pytest.mark.garde_fou
def test_backend_systemd_est_actif(edge) -> None:
    service = edge.run("systemctl is-active pub-fichier-backend.service")
    response = edge.run(
        "curl --max-time 5 --silent --show-error "
        "http://127.0.0.1:18081/"
    )
    assert (
        service.rc == 0
        and service.stdout.strip() == "active"
        and "systemd backend is healthy" in response.stdout
    ), message(
        en="The systemd-managed backend is not active and responding on port 18081.",
        fr="Le backend géré par systemd n'est pas actif et ne répond pas sur le port 18081.",
    )


def test_route_dynamique_sert_le_backend_systemd(edge) -> None:
    response = _route(edge)
    assert (
        response.rc == 0
        and "HTTP=200" in response.stdout
        and "systemd backend is healthy" in response.stdout
    ), message(
        en=f"Traefik did not route Host {HOTE} to the systemd backend "
        f"(HTTP result: {response.stdout.strip() or 'no response'}).",
        fr=f"Traefik n'a pas routé l'hôte {HOTE} vers le backend systemd "
        f"(résultat HTTP : {response.stdout.strip() or 'aucune réponse'}).",
    )


def test_configuration_chargee_sans_redemarrer_traefik(edge) -> None:
    expected = edge.run(f"cat {WORK}/traefik-started-at")
    actual = edge.run(
        "docker inspect --format '{{.State.StartedAt}}' pub-fichier-traefik"
    )
    route = _route(edge)
    assert (
        expected.rc == 0
        and actual.rc == 0
        and actual.stdout.strip() == expected.stdout.strip()
        and route.rc == 0
    ), message(
        en="The route must become available through dynamic configuration "
        "without restarting the original Traefik container.",
        fr="La route doit devenir accessible par configuration dynamique "
        "sans redémarrer le conteneur Traefik initial.",
    )
