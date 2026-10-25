"""Verify Traefik administration and Docker API access are protected."""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
HOTE = "admin.lab.test"
CA = "/opt/pub-admin/admin.crt"
IDENTIFIANT = "operator:Securite-Lab-2026"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _requete(edge, chemin: str, authentifie: bool = False):
    auth = f"--user '{IDENTIFIANT}'" if authentifie else ""
    return edge.run(
        f"curl --max-time 5 --silent --show-error --output /tmp/pub-admin-response "
        f"--write-out '%{{http_code}}' --cacert {CA} "
        f"--resolve {HOTE}:443:127.0.0.1 {auth} "
        f"https://{HOTE}{chemin}"
    )


def test_aucun_acces_direct_sur_le_port_8080(edge) -> None:
    res = edge.run("ss -ltnH 'sport = :8080'")
    assert not res.stdout.strip(), message(
        en=f"Traefik administration is still listening directly on host port "
        f"8080: {res.stdout.strip()!r}.",
        fr=f"L'administration Traefik écoute encore directement sur le port "
        f"8080 de l'hôte : {res.stdout.strip()!r}.",
    )


@pytest.mark.parametrize("chemin", ["/dashboard/", "/api/overview"])
def test_administration_refuse_les_requetes_sans_identifiants(edge, chemin) -> None:
    res = _requete(edge, chemin)
    assert res.rc == 0 and res.stdout.strip() == "401", message(
        en=f"Unauthenticated HTTPS request to {chemin} returned HTTP "
        f"{res.stdout.strip() or 'no response'} (curl rc={res.rc}); expected 401.",
        fr=f"La requête HTTPS sans identifiants vers {chemin} a renvoyé HTTP "
        f"{res.stdout.strip() or 'aucune réponse'} (curl rc={res.rc}) ; il fallait 401.",
    )


@pytest.mark.parametrize("chemin", ["/dashboard/", "/api/overview"])
def test_operateur_authentifie_accede_a_l_administration(edge, chemin) -> None:
    res = _requete(edge, chemin, authentifie=True)
    assert res.rc == 0 and res.stdout.strip() == "200", message(
        en=f"Authenticated HTTPS request to {chemin} returned HTTP "
        f"{res.stdout.strip() or 'no response'} (curl rc={res.rc}); "
        "expected 200 with a certificate trusted for admin.lab.test.",
        fr=f"La requête HTTPS authentifiée vers {chemin} a renvoyé HTTP "
        f"{res.stdout.strip() or 'aucune réponse'} (curl rc={res.rc}) ; "
        "il fallait 200 avec un certificat de confiance pour admin.lab.test.",
    )


def test_reponses_administration_portent_les_entetes_de_securite(edge) -> None:
    result = edge.run(
        f"curl --max-time 5 --silent --show-error --dump-header "
        f"/tmp/pub-admin-headers --output /dev/null --write-out '%{{http_code}}' "
        f"--cacert {CA} --resolve {HOTE}:443:127.0.0.1 "
        f"--user '{IDENTIFIANT}' https://{HOTE}/api/overview && "
        "tr -d '\\r' < /tmp/pub-admin-headers | "
        "grep -Eiq '^x-content-type-options: nosniff$' && "
        "tr -d '\\r' < /tmp/pub-admin-headers | "
        "grep -Eiq '^x-frame-options: DENY$'"
    )
    assert result.rc == 0 and result.stdout.strip() == "200", message(
        en="Authenticated administration must return HTTP 200 with "
        "X-Content-Type-Options: nosniff and X-Frame-Options: DENY.",
        fr="L'administration authentifiée doit répondre HTTP 200 avec "
        "X-Content-Type-Options: nosniff et X-Frame-Options: DENY.",
    )


def test_api_docker_passe_par_un_proxy_de_socket_restreint(edge) -> None:
    traefik_mounts = edge.run(
        "docker inspect --format '{{json .Mounts}}' pub-admin-traefik"
    )
    traefik_cmd = edge.run(
        "docker inspect --format '{{range .Config.Cmd}}{{println .}}{{end}}' "
        "pub-admin-traefik"
    )
    proxy_image = edge.run(
        "docker inspect --format '{{.Config.Image}}' pub-admin-socket-proxy"
    )
    expected_image = edge.run("cat /opt/pub-admin/socket-proxy-image")
    proxy_state = edge.run(
        "docker inspect --format '{{.State.Running}}' pub-admin-socket-proxy"
    )
    proxy_env = edge.run(
        "docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "
        "pub-admin-socket-proxy"
    )
    assert (
        traefik_mounts.rc == 0
        and "/var/run/docker.sock" not in traefik_mounts.stdout
        and traefik_cmd.rc == 0
        and "--providers.docker.endpoint=tcp://pub-admin-socket-proxy:2375"
        in traefik_cmd.stdout
        and proxy_image.rc == 0
        and proxy_image.stdout.strip() == expected_image.stdout.strip()
        and "@sha256:" in proxy_image.stdout
        and proxy_state.rc == 0
        and proxy_state.stdout.strip() == "true"
        and proxy_env.rc == 0
        and all(
            f"{setting}=1" in proxy_env.stdout.splitlines()
            for setting in ("CONTAINERS", "EVENTS", "PING", "VERSION")
        )
        and "POST=0" in proxy_env.stdout.splitlines()
    ), message(
        en="Traefik must use the pinned, running Docker socket proxy, which "
        "allows only read-only provider endpoints, and must not mount "
        "/var/run/docker.sock directly.",
        fr="Traefik doit utiliser le proxy de socket Docker épinglé et actif, "
        "limité aux points d'accès en lecture seule, sans monter directement "
        "/var/run/docker.sock.",
    )


def test_limitation_debit_renvoie_429_sous_charge(edge) -> None:
    result = edge.run(
        "seq 1 12 | xargs -P 12 -I{} curl --max-time 5 --silent "
        "--show-error --output /dev/null --write-out '%{http_code}\\n' "
        f"--cacert {CA} --resolve {HOTE}:443:127.0.0.1 "
        f"--user '{IDENTIFIANT}' https://{HOTE}/api/overview"
    )
    codes = result.stdout.splitlines()
    assert result.rc == 0 and "429" in codes, message(
        en=f"A burst of 12 authenticated requests did not trigger HTTP 429 "
        f"(curl rc={result.rc}, observed codes={codes!r}).",
        fr=f"Une rafale de 12 requêtes authentifiées n'a pas déclenché HTTP 429 "
        f"(curl rc={result.rc}, codes observés={codes!r}).",
    )
