"""Verify the running Traefik upgrade, route, and rollback path."""

from __future__ import annotations

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
COMPOSE_DIR = "/opt/pub-mise-a-jour"
CONTENEUR = "pub-mise-a-jour-traefik"
IMAGE_CIBLE = (
    "traefik:v3.7.15@"
    "sha256:0f6150202bc1fed72a7bd2107460eaa510e5b8a905f3fdb5b84f2c8619c33368"
)
IMAGE_PRECEDENTE = (
    "traefik:v3.7.6@"
    "sha256:21a3d83696379bac6434bb32e1dde0aff0e84ef2abd053ed3db87d3f45e749b2"
)


def _version(edge, version: str):
    return edge.run(
        "for attempt in $(seq 1 30); do "
        f"output=$(docker exec {CONTENEUR} traefik version 2>/dev/null || true); "
        f"if printf '%s' \"$output\" | grep -Fq '{version}'; then "
        "printf '%s\\n' \"$output\"; exit 0; fi; "
        "sleep 1; done; printf '%s\\n' \"$output\"; exit 1"
    )


def test_traefik_sert_la_version_cible_epinglee() -> None:
    edge = lab_host(CIBLE)
    image = edge.run(
        f"docker inspect --format '{{{{.Config.Image}}}}' {CONTENEUR}"
    )
    version = _version(edge, "3.7.15")
    assert (
        image.rc == 0
        and image.stdout.strip() == IMAGE_CIBLE
        and version.rc == 0
    ), message(
        en="The running container must use the pinned v3.7.15 image and report "
        "that version.",
        fr="Le conteneur actif doit utiliser l'image v3.7.15 épinglée et "
        "annoncer cette version.",
    )


def test_configuration_et_service_repondent_apres_la_mise_a_niveau() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "curl --max-time 5 --silent --show-error --resolve "
        "upgrade.lab.test:80:127.0.0.1 --output /dev/null "
        "--write-out '%{http_code}' http://upgrade.lab.test/"
    )
    assert result.rc == 0 and result.stdout.strip() == "200", message(
        en="The upgraded proxy must load its configuration and serve the "
        "backend at upgrade.lab.test with HTTP 200.",
        fr="Le proxy mis à niveau doit charger sa configuration et publier le "
        "backend sur upgrade.lab.test en HTTP 200.",
    )


def test_retour_arriere_reussi_puis_version_cible_restauree() -> None:
    edge = lab_host(CIBLE)
    rollback_image = edge.run(
        f"cd {COMPOSE_DIR} && docker compose -f compose.yaml "
        "-f compose.rollback.yaml config --images"
    )
    assert (
        rollback_image.rc == 0
        and rollback_image.stdout.strip() == IMAGE_PRECEDENTE
    ), message(
        en="The rollback Compose override must pin the original v3.7.6 image.",
        fr="La surcharge Compose de retour arrière doit épingler l'image "
        "d'origine v3.7.6.",
    )

    rollback = edge.run(
        f"cd {COMPOSE_DIR} && docker compose -f compose.yaml "
        "-f compose.rollback.yaml up -d"
    )
    rolled_back_version = _version(edge, "3.7.6")
    restore = edge.run(
        f"cd {COMPOSE_DIR} && docker compose -f compose.yaml up -d"
    )
    restored_version = _version(edge, "3.7.15")
    assert (
        rollback.rc == 0
        and rolled_back_version.rc == 0
        and restore.rc == 0
        and restored_version.rc == 0
    ), message(
        en="The proxy must run v3.7.6 during rollback, then return to v3.7.15.",
        fr="Le proxy doit utiliser la v3.7.6 pendant le retour arrière, puis "
        "revenir à la v3.7.15.",
    )
