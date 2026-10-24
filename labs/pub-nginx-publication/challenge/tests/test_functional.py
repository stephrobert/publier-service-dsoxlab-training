"""Verify Nginx publishes the local application with proxy headers."""

from __future__ import annotations

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")


def test_nginx_preserve_le_chemin_et_les_entetes_du_proxy() -> None:
    result = lab_host(CIBLE).run(
        "curl --max-time 5 --silent --show-error "
        "--resolve app.lab.test:80:127.0.0.1 "
        "http://app.lab.test/health?probe=nginx"
    )
    assert (
        result.rc == 0
        and "Nginx backend: /health?probe=nginx" in result.stdout
        and "Host: app.lab.test" in result.stdout
        and "X-Forwarded-For: 127.0.0.1" in result.stdout
        and "X-Forwarded-Proto: http" in result.stdout
    ), message(
        en="Nginx must proxy the request to the local application, preserve "
        "its path and host, and set both forwarding headers.",
        fr="Nginx doit transmettre la requête à l'application locale, "
        "préserver son chemin et son hôte, et renseigner les deux en-têtes "
        "de transfert.",
    )
