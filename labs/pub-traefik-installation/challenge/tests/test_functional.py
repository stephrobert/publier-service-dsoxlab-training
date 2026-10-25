"""Verify Traefik's install: real version, closed-by-default listening,
diagnosable invalid configuration, and reboot persistence."""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
UNITE = "pub-installation-traefik.service"
CONTENEUR = "pub-installation-traefik"
WORK = "/opt/pub-installation"
DYNAMIC = f"{WORK}/dynamic"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host("poste.lab")


def _unite_active(edge) -> bool:
    return edge.run(f"systemctl is-active {UNITE}").stdout.strip() == "active"


def _attendre_port_80(hote, limite_s: float = 60.0) -> bool:
    limite = time.monotonic() + limite_s
    while time.monotonic() < limite:
        res = hote.run(
            "curl --max-time 2 --silent --show-error --output /dev/null "
            "--write-out '%{http_code}' http://edge.lab:80/ || true"
        )
        if res.stdout.strip() in {"404", "200"}:
            return True
        time.sleep(2)
    return False


def test_version_provenance_du_conteneur_reel(edge) -> None:
    attendu = edge.run(f"cat {WORK}/image-ref").stdout.strip()
    inspecte = edge.run(
        f"docker inspect --format '{{{{.Image}}}}' {CONTENEUR}"
    )
    digeste_ok = False
    if inspecte.rc == 0 and inspecte.stdout.strip():
        digeste = edge.run(
            "docker image inspect --format '{{json .RepoDigests}}' "
            f"{inspecte.stdout.strip()}"
        )
        digeste_ok = digeste.rc == 0 and attendu.split("@")[-1] in digeste.stdout
    assert inspecte.rc == 0 and attendu and digeste_ok, message(
        en=f"The running container {CONTENEUR} is not the pinned image "
        f"{attendu}; read the real executed image, not a file's tag.",
        fr=f"Le conteneur en cours {CONTENEUR} n'est pas l'image épinglée "
        f"{attendu} ; lisez l'image réellement exécutée, pas le tag d'un fichier.",
    )


def test_seul_le_point_entree_web_ecoute_depuis_le_client(edge, poste) -> None:
    web = poste.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' http://edge.lab:80/"
    )
    api = poste.run(
        "curl --max-time 3 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' http://edge.lab:8080/api/overview "
        "|| echo refuse"
    )
    assert web.stdout.strip() in {"404", "200"} and (
        api.rc != 0 or api.stdout.strip() == "refuse" or api.stdout.strip() not in {"200"}
    ), message(
        en="The web entrypoint must answer on port 80, and the dashboard/API "
        f"on 8080 must not be reachable from poste.lab (web={web.stdout!r}, "
        f"api={api.stdout!r}).",
        fr="Le point d'entrée web doit répondre sur le port 80, et le "
        "dashboard/API sur le port 8080 ne doit pas être joignable depuis "
        f"poste.lab (web={web.stdout!r}, api={api.stdout!r}).",
    )


def test_configuration_invalide_journalisee_sans_crash(edge) -> None:
    demarre_avant = edge.run(
        f"docker inspect --format '{{{{.State.StartedAt}}}}' {CONTENEUR}"
    ).stdout.strip()
    edge.run(
        f"echo 'http: {{routers: {{cassee: {{rule: Host(' > {DYNAMIC}/invalide.yaml"
    )
    time.sleep(3)
    toujours_actif = _unite_active(edge)
    demarre_apres = edge.run(
        f"docker inspect --format '{{{{.State.StartedAt}}}}' {CONTENEUR}"
    ).stdout.strip()
    journal = edge.run(f"docker logs {CONTENEUR} --tail 50").stdout.lower()
    edge.run(f"rm -f {DYNAMIC}/invalide.yaml")
    time.sleep(2)
    assert (
        toujours_actif
        and demarre_avant == demarre_apres
        and any(mot in journal for mot in ("error", "erreur", "invalid"))
    ), message(
        en="An invalid dynamic configuration file must be rejected with a "
        "diagnosable log entry, without restarting or crashing the Traefik "
        "process.",
        fr="Un fichier de configuration dynamique invalide doit être refusé "
        "avec une entrée de journal exploitable, sans redémarrer ni faire "
        "planter le processus Traefik.",
    )


def test_point_entree_persiste_apres_reboot(edge, poste) -> None:
    avant = edge.run(
        f"docker inspect --format '{{{{.Image}}}}' {CONTENEUR}"
    ).stdout.strip()
    assert avant, message(
        en="Traefik must be running before the reboot is attempted.",
        fr="Traefik doit tourner avant de tenter le redémarrage.",
    )
    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)

    limite = time.monotonic() + 180
    revenu = False
    while time.monotonic() < limite:
        res = edge.run("echo up")
        if res.rc == 0 and "up" in res.stdout:
            revenu = True
            break
        time.sleep(5)

    assert revenu, message(
        en="edge.lab did not come back online within 180s after reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180s après le redémarrage.",
    )

    actif = _unite_active(edge)
    joignable = _attendre_port_80(poste)
    assert actif and joignable, message(
        en=f"After reboot, {UNITE} must be active and the web entrypoint "
        "reachable again from poste.lab, without replaying setup.",
        fr=f"Après redémarrage, {UNITE} doit être actif et le point d'entrée "
        "web de nouveau joignable depuis poste.lab, sans rejouer le setup.",
    )
