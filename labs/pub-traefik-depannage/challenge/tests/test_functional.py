"""Verify repaired Traefik routes, TLS certificate, and redirects."""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")


def test_route_manquante_ne_renvoie_plus_404() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' -H 'Host: notfound.lab.test' "
        "http://127.0.0.1/"
    )
    assert result.rc == 0 and result.stdout.strip() == "200", message(
        en="The notfound route must match the requested host and return HTTP 200.",
        fr="La route notfound doit correspondre à l'hôte demandé et répondre "
        "HTTP 200.",
    )


def test_service_injoignable_ne_renvoie_plus_502() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' -H 'Host: badgateway.lab.test' "
        "http://127.0.0.1/"
    )
    assert result.rc == 0 and result.stdout.strip() == "200", message(
        en="The badgateway route must reach its live backend and return HTTP 200.",
        fr="La route badgateway doit joindre son backend actif et répondre "
        "HTTP 200.",
    )


def test_delai_backend_est_adapte_et_ne_renvoie_plus_504() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "curl --max-time 10 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' -H 'Host: timeout.lab.test' "
        "http://127.0.0.1/slow"
    )
    assert result.rc == 0 and result.stdout.strip() == "200", message(
        en="The slow backend must be allowed to respond before the proxy "
        "timeout and return HTTP 200.",
        fr="Le backend lent doit pouvoir répondre avant l'expiration du délai "
        "du proxy et renvoyer HTTP 200.",
    )


def test_certificat_servi_correspond_au_nom_tls() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "timeout 8 openssl s_client -connect 127.0.0.1:443 "
        "-servername tls.lab.test </dev/null 2>/dev/null | "
        "openssl x509 -noout -ext subjectAltName"
    )
    assert (
        result.rc == 0 and "DNS:tls.lab.test" in result.stdout
    ), message(
        en="The certificate served for tls.lab.test must include "
        "DNS:tls.lab.test in its subject alternative names.",
        fr="Le certificat servi pour tls.lab.test doit inclure "
        "DNS:tls.lab.test dans ses noms alternatifs.",
    )


def test_redirect_http_https_n_est_pas_une_boucle() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "curl --max-time 10 --silent --show-error --location --insecure "
        "--max-redirs 5 --output /dev/null --write-out '%{http_code} "
        "%{num_redirects}' --resolve loop.lab.test:80:127.0.0.1 "
        "--resolve loop.lab.test:443:127.0.0.1 http://loop.lab.test/"
    )
    assert result.rc == 0 and result.stdout.strip() == "200 1", message(
        en="HTTP must redirect once to HTTPS, then serve HTTP 200 without "
        "a redirect loop.",
        fr="HTTP doit rediriger une fois vers HTTPS, puis servir HTTP 200 "
        "sans boucle de redirection.",
    )


@pytest.mark.garde_fou
def test_traefik_n_a_pas_ete_redemarre() -> None:
    edge = lab_host(CIBLE)
    expected = edge.run("cat /opt/pub-depannage/traefik-started-at")
    actual = edge.run(
        "docker inspect --format '{{.State.StartedAt}}' pub-depannage-traefik"
    )
    assert (
        expected.rc == 0
        and actual.rc == 0
        and actual.stdout.strip() == expected.stdout.strip()
    ), message(
        en="Traefik must stay up while its dynamic file-provider configuration changes.",
        fr="Traefik doit rester actif pendant les changements dynamiques du "
        "fournisseur fichier.",
    )
