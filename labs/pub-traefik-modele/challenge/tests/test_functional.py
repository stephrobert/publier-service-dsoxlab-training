"""Verify routing associations across Traefik's file and Docker providers."""

from __future__ import annotations

import secrets

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _get(edge, host: str, path: str = "/") -> object:
    return edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/stdout "
        f"--write-out '\\nHTTP=%{{http_code}}' -H 'Host: {host}' "
        f"http://127.0.0.1{path}"
    )


def test_chemin_route_modele_a_vers_app_a(edge) -> None:
    response = _get(edge, "modele-a.lab.test", "/un/chemin/quelconque")
    assert (
        response.rc == 0
        and "HTTP=200" in response.stdout
        and "Hostname: app-a" in response.stdout
    ), message(
        en="modele-a.lab.test must reach backend app-a through the router's "
        f"service association (response: {response.stdout.strip() or 'none'}).",
        fr="modele-a.lab.test doit atteindre le backend app-a via l'association "
        f"service du routeur (réponse : {response.stdout.strip() or 'aucune'}).",
    )


def test_provider_qualifie_route_modele_b_vers_app_b(edge) -> None:
    response = _get(edge, "modele-b.lab.test")
    assert (
        response.rc == 0
        and "HTTP=200" in response.stdout
        and "Hostname: app-b" in response.stdout
    ), message(
        en="modele-b.lab.test must reach the Docker-provider service "
        "'cible', qualified as cible@docker, not the file-provider decoy "
        f"of the same name (response: {response.stdout.strip() or 'none'}).",
        fr="modele-b.lab.test doit atteindre le service 'cible' du provider "
        "Docker, qualifié en cible@docker, pas le leurre de même nom du "
        f"provider fichier (réponse : {response.stdout.strip() or 'aucune'}).",
    )


def test_inconnu_n_atteint_aucune_application(edge) -> None:
    nom = f"{secrets.token_hex(8)}.lab.test"
    response = _get(edge, nom)
    assert (
        response.rc == 0 and "HTTP=404" in response.stdout
    ), message(
        en=f"An unplanned hostname ({nom}) must reach no application (404), "
        f"but Traefik answered: {response.stdout.strip() or 'no response'}. "
        "Remove the catch-all router.",
        fr=f"Un nom non prévu ({nom}) ne doit atteindre aucune application "
        f"(404), or Traefik a répondu : {response.stdout.strip() or 'aucune réponse'}. "
        "Supprimez le routeur attrape-tout.",
    )
