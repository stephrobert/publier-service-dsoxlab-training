"""Verify service availability and recovery after a Docker daemon restart."""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
URL = "http://127.0.0.1:18080/"
CONTENEUR = "pub-restart-whoami"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _requete(edge):
    return edge.run(
        f"curl --max-time 5 --silent --show-error --output /tmp/pub-restart-body "
        f"--write-out '%{{http_code}}' {URL}"
    )


def test_service_repond_avant_le_redemarrage(edge) -> None:
    res = _requete(edge)
    corps = edge.run("cat /tmp/pub-restart-body")
    assert (
        res.rc == 0
        and res.stdout.strip() == "200"
        and "Hostname:" in corps.stdout
    ), message(
        en=f"The service did not answer HTTP 200 on port 18080 "
        f"(curl rc={res.rc}, HTTP {res.stdout.strip() or 'no response'}).",
        fr=f"Le service ne répond pas en HTTP 200 sur le port 18080 "
        f"(curl rc={res.rc}, HTTP {res.stdout.strip() or 'aucune réponse'}).",
    )


def test_conteneur_configure_pour_redemarrer_avec_docker(edge) -> None:
    res = edge.run(
        f"docker inspect --format '{{{{.HostConfig.RestartPolicy.Name}}}}' {CONTENEUR}"
    )
    assert res.rc == 0 and res.stdout.strip() in {"always", "unless-stopped"}, message(
        en=f"{CONTENEUR} has no automatic Docker restart policy "
        f"(inspect rc={res.rc}, policy={res.stdout.strip() or 'missing'}).",
        fr=f"{CONTENEUR} n'a pas de politique de redémarrage automatique "
        f"(inspect rc={res.rc}, politique={res.stdout.strip() or 'absente'}).",
    )


def test_service_revient_apres_redemarrage_du_moteur_docker(edge) -> None:
    avant = _requete(edge)
    assert avant.rc == 0 and avant.stdout.strip() == "200", message(
        en="The service must answer before Docker is restarted.",
        fr="Le service doit répondre avant le redémarrage de Docker.",
    )

    redemarrage = edge.run(
        "sudo systemctl restart docker && "
        "for _ in $(seq 1 30); do "
        "if curl --max-time 2 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' "
        f"{URL} | grep -qx 200; then exit 0; fi; "
        "sleep 1; done; exit 1"
    )
    assert redemarrage.rc == 0, message(
        en=f"The HTTP endpoint did not recover within 30 seconds after the "
        f"Docker daemon restarted (rc={redemarrage.rc}).",
        fr=f"L'endpoint HTTP n'a pas récupéré dans les 30 secondes après le "
        f"redémarrage du moteur Docker (rc={redemarrage.rc}).",
    )
