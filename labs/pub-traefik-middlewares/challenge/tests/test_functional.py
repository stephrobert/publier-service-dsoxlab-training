"""Verify Traefik middleware behavior through real HTTP responses."""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
HOTE = "middleware.lab.test"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def test_prefixe_est_retire_avant_le_backend(edge) -> None:
    result = edge.run(
        "curl --max-time 5 --silent --show-error --output /tmp/pub-middlewares-path "
        "--write-out '%{http_code}' "
        f"-H 'Host: {HOTE}' http://127.0.0.1/portal/path-check && "
        "printf '\\n' && head -n 1 /tmp/pub-middlewares-path"
    )
    assert result.rc == 0 and result.stdout.splitlines()[-1:] == ["PATH=/path-check"], message(
        en="The backend must receive /path-check for a request to /portal/path-check.",
        fr="Le backend doit recevoir /path-check pour une requête vers /portal/path-check.",
    )


def test_ancienne_url_est_redirigee_permanemment(edge) -> None:
    result = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--dump-header /tmp/pub-middlewares-redirect "
        "--write-out '%{http_code}' "
        f"-H 'Host: {HOTE}' http://127.0.0.1/legacy/guide && "
        "tr -d '\\r' < /tmp/pub-middlewares-redirect | "
        "grep -Fqi 'Location: http://middleware.lab.test/docs/guide'"
    )
    assert result.rc == 0 and result.stdout.strip() == "301", message(
        en="A request to /legacy/guide must return HTTP 301 and redirect to "
        "http://middleware.lab.test/docs/guide.",
        fr="Une requête vers /legacy/guide doit répondre HTTP 301 et rediriger "
        "vers http://middleware.lab.test/docs/guide.",
    )


def test_reponses_portail_portent_les_entetes_de_securite(edge) -> None:
    result = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--dump-header /tmp/pub-middlewares-headers "
        f"-H 'Host: {HOTE}' http://127.0.0.1/portal/path-check && "
        "tr -d '\\r' < /tmp/pub-middlewares-headers | "
        "grep -Eiq '^x-content-type-options: nosniff$' && "
        "tr -d '\\r' < /tmp/pub-middlewares-headers | "
        "grep -Eiq '^x-frame-options: DENY$'"
    )
    assert result.rc == 0, message(
        en="Portal responses must include X-Content-Type-Options: nosniff and "
        "X-Frame-Options: DENY.",
        fr="Les réponses du portail doivent inclure X-Content-Type-Options: "
        "nosniff et X-Frame-Options: DENY.",
    )


def test_reponse_portail_est_compressee_pour_un_client_compatible(edge) -> None:
    result = edge.run(
        "curl --max-time 5 --silent --show-error --compressed "
        "--output /tmp/pub-middlewares-compressed "
        "--dump-header /tmp/pub-middlewares-compressed-headers "
        "--write-out '%{http_code}' "
        f"-H 'Host: {HOTE}' http://127.0.0.1/portal/compressed && "
        "tr -d '\\r' < /tmp/pub-middlewares-compressed-headers | "
        "grep -Eiq '^content-encoding: gzip$' && "
        "printf '\\n' && head -n 1 /tmp/pub-middlewares-compressed"
    )
    assert (
        result.rc == 0
        and result.stdout.splitlines()[0] == "200"
        and result.stdout.splitlines()[-1:] == ["PATH=/compressed"]
    ), message(
        en="A gzip-capable client must receive a compressed HTTP 200 response "
        "and the backend must see /compressed.",
        fr="Un client compatible gzip doit recevoir une réponse HTTP 200 "
        "compressée et le backend doit voir /compressed.",
    )


@pytest.mark.garde_fou
def test_traefik_n_a_pas_ete_redemarre(edge) -> None:
    expected = edge.run("cat /opt/pub-middlewares/traefik-started-at")
    actual = edge.run(
        "docker inspect --format '{{.State.StartedAt}}' pub-middlewares-traefik"
    )
    assert (
        expected.rc == 0
        and actual.rc == 0
        and actual.stdout.strip() == expected.stdout.strip()
    ), message(
        en="Traefik must stay available while its dynamic middleware configuration changes.",
        fr="Traefik doit rester disponible pendant la modification dynamique de ses middlewares.",
    )
