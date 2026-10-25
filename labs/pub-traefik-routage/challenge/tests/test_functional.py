"""Verify route priorities, scope, cross-provider qualification, and
robustness to a later dynamic change."""

from __future__ import annotations

import secrets

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
WORK = "/opt/pub-routage"
DYNAMIC = f"{WORK}/dynamic"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _get(edge, host: str, path: str = "/") -> object:
    return edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/stdout "
        f"--write-out '\\nHTTP=%{{http_code}}' --dump-header /dev/stderr "
        f"-H 'Host: {host}' http://127.0.0.1{path} 2>&1"
    )


def test_priorite_matrice_host_et_chemin(edge) -> None:
    racine = _get(edge, "routage.lab.test", "/")
    v2 = _get(edge, "routage.lab.test", "/v2")
    v2_sous_chemin = _get(
        edge, "routage.lab.test", f"/v2/items?x={secrets.token_hex(3)}"
    )
    assert (
        "HTTP=200" in racine.stdout
        and "Hostname: api-v1" in racine.stdout
        and "HTTP=200" in v2.stdout
        and "Hostname: api-v2" in v2.stdout
        and "HTTP=200" in v2_sous_chemin.stdout
        and "Hostname: api-v2" in v2_sous_chemin.stdout
    ), message(
        en="routage.lab.test/ must reach api-v1 and routage.lab.test/v2* "
        "must reach api-v2: fix the router priorities so the more specific "
        f"rule wins (root: {racine.stdout!r}, /v2: {v2.stdout!r}).",
        fr="routage.lab.test/ doit atteindre api-v1 et routage.lab.test/v2* "
        "doit atteindre api-v2 : corrigez les priorités des routeurs pour "
        f"que la règle la plus spécifique l'emporte (racine : {racine.stdout!r}, "
        f"/v2 : {v2.stdout!r}).",
    )


def test_qualification_catalogue_service_et_middleware(edge) -> None:
    response = _get(edge, "catalogue.routage.lab.test")
    assert (
        "HTTP=200" in response.stdout
        and "Hostname: catalogue" in response.stdout
        and "X-Marque: docker" in response.stdout
    ), message(
        en="catalogue.routage.lab.test must reach the Docker-provider "
        "catalog and carry its X-Marque: docker header; qualify the service "
        "and middleware as cible@docker and marque@docker "
        f"(response: {response.stdout!r}).",
        fr="catalogue.routage.lab.test doit atteindre le catalogue du "
        "provider Docker et porter son en-tête X-Marque: docker ; qualifiez "
        "le service et le middleware en cible@docker et marque@docker "
        f"(réponse : {response.stdout!r}).",
    )


def test_defaut_admin_scope_au_bon_hote(edge) -> None:
    hote_aleatoire = f"{secrets.token_hex(8)}.lab.test"
    fuite = _get(edge, hote_aleatoire, "/admin")
    autorise = _get(edge, "routage.lab.test", "/admin")
    assert (
        "HTTP=404" in fuite.stdout
        and "Hostname: admin" not in fuite.stdout
        and "HTTP=200" in autorise.stdout
        and "Hostname: admin" in autorise.stdout
    ), message(
        en=f"/admin must reach the admin app only on routage.lab.test, not "
        f"on an arbitrary hostname ({hote_aleatoire}); scope the admin "
        f"router with Host(`routage.lab.test`) (leak: {fuite.stdout!r}, "
        f"authorized: {autorise.stdout!r}).",
        fr=f"/admin ne doit atteindre l'application admin que sur "
        f"routage.lab.test, pas sur un nom d'hôte arbitraire ({hote_aleatoire}) ; "
        f"restreignez le routeur admin avec Host(`routage.lab.test`) "
        f"(fuite : {fuite.stdout!r}, autorisé : {autorise.stdout!r}).",
    )


def test_changement_dynamique_ne_casse_pas_les_routes(edge) -> None:
    demarre_avant = edge.run(
        "docker inspect --format '{{.State.StartedAt}}' pub-routage-traefik"
    ).stdout.strip()

    edge.run(
        "printf '%s\\n' "
        "'http:' "
        "'  routers:' "
        "'    nouveau:' "
        "'      rule: Host(`nouveau.routage.lab.test`)' "
        "'      entryPoints: [web]' "
        "'      service: api-v1' "
        f"> {DYNAMIC}/nouveau.yaml"
    )
    import time

    time.sleep(3)

    racine = _get(edge, "routage.lab.test", "/")
    v2 = _get(edge, "routage.lab.test", "/v2")
    nouveau = _get(edge, "nouveau.routage.lab.test", "/")
    demarre_apres = edge.run(
        "docker inspect --format '{{.State.StartedAt}}' pub-routage-traefik"
    ).stdout.strip()

    edge.run(f"rm -f {DYNAMIC}/nouveau.yaml")

    assert (
        "HTTP=200" in racine.stdout
        and "Hostname: api-v1" in racine.stdout
        and "HTTP=200" in v2.stdout
        and "Hostname: api-v2" in v2.stdout
        and "HTTP=200" in nouveau.stdout
        and demarre_avant == demarre_apres
        and demarre_avant != ""
    ), message(
        en="Adding an unrelated router dynamically must not break the "
        "existing routes nor restart Traefik "
        f"(root: {racine.stdout!r}, /v2: {v2.stdout!r}, new: {nouveau.stdout!r}).",
        fr="Ajouter un routeur sans rapport dynamiquement ne doit casser ni "
        "les routes existantes ni redémarrer Traefik "
        f"(racine : {racine.stdout!r}, /v2 : {v2.stdout!r}, nouveau : {nouveau.stdout!r}).",
    )
