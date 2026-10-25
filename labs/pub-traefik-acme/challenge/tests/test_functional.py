"""Verify automatic ACME renewal and the certificate served by Traefik."""

from __future__ import annotations

import re
import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
HOTE = "app.lab.test"
URL = "https://app.lab.test/"
PEBBLE = "pub-renewal-pebble"
AUTORITE = "/opt/pub-traefik-acme/pebble-root.pem"
DELAI_DEMARRAGE_S = 45
DELAI_RENOUVELLEMENT_S = 120


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def test_stockage_acme_a_des_permissions_strictes(edge) -> None:
    result = edge.run("stat -c '%a' /opt/pub-traefik-acme/acme.json")
    assert result.rc == 0 and result.stdout.strip() == "600", message(
        en=f"ACME storage permissions are {result.stdout.strip() or 'missing'}, "
        "not 600.",
        fr=f"Les permissions du stockage ACME sont "
        f"{result.stdout.strip() or 'absentes'}, et non 600.",
    )


def test_http_est_redirige_vers_https(edge) -> None:
    result = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--write-out '%{http_code} %{redirect_url}' "
        "--resolve app.lab.test:80:127.0.0.1 http://app.lab.test/"
    )
    status, _, destination = result.stdout.strip().partition(" ")
    assert result.rc == 0 and status == "301" and destination.startswith(
        "https://app.lab.test/"
    ), message(
        en=f"HTTP did not redirect to HTTPS with status 301 "
        f"(curl rc={result.rc}, result={result.stdout.strip() or 'no response'}).",
        fr=f"HTTP n'a pas été redirigé vers HTTPS avec le statut 301 "
        f"(curl rc={result.rc}, résultat={result.stdout.strip() or 'aucune réponse'}).",
    )


def test_tls_10_et_11_sont_refuses(edge) -> None:
    moderne = edge.run(
        f"curl --max-time 5 --silent --show-error --output /dev/null "
        f"--tlsv1.2 --tls-max 1.2 --cacert {AUTORITE} "
        f"--resolve {HOTE}:443:127.0.0.1 {URL}"
    )
    assert moderne.rc == 0, message(
        en="A trusted TLS 1.2 request failed; cannot assess legacy TLS rejection "
        f"(curl rc={moderne.rc}).",
        fr="La requête TLS 1.2 de confiance a échoué ; impossible d'évaluer le "
        f"refus des anciennes versions TLS (curl rc={moderne.rc}).",
    )

    results = {
        version: edge.run(
            f"curl --max-time 5 --silent --show-error --output /dev/null "
            f"--tlsv{version} --tls-max {version} --cacert {AUTORITE} "
            f"--resolve {HOTE}:443:127.0.0.1 {URL}"
        )
        for version in ("1.0", "1.1")
    }
    acceptes = [version for version, result in results.items() if result.rc == 0]
    assert not acceptes, message(
        en=f"Traefik accepted obsolete TLS version(s): {', '.join(acceptes)}.",
        fr=f"Traefik a accepté les anciennes versions TLS : {', '.join(acceptes)}.",
    )


def _emissions(edge) -> list[str]:
    journal = edge.run(f"docker logs {PEBBLE} 2>&1")
    return [
        serie.lower().lstrip("0")
        for serie in re.findall(
            r"Issued certificate serial ([0-9a-fA-F]+)", journal.stdout
        )
    ]


def _certificat_servi(edge) -> tuple[str | None, str]:
    result = edge.run(
        f"timeout 8 openssl s_client -connect 127.0.0.1:443 -servername {HOTE} "
        "</dev/null 2>/dev/null | "
        "openssl x509 -noout -serial -enddate -ext subjectAltName"
    )
    if result.rc != 0:
        return None, result.stdout + result.stderr
    match = re.search(r"^serial=([0-9a-fA-F]+)$", result.stdout, re.M)
    return (match.group(1).lower().lstrip("0") if match else None), result.stdout


def test_traefik_renouvelle_et_sert_le_nouveau_certificat(edge) -> None:
    echeance_demarrage = time.monotonic() + DELAI_DEMARRAGE_S
    dernier_http = None
    serial_servi = None
    details_certificat = ""
    emissions: list[str] = []

    while time.monotonic() < echeance_demarrage:
        client = edge.run(
            f"curl --max-time 5 --silent --show-error --cacert {AUTORITE} "
            f"--resolve {HOTE}:443:127.0.0.1 {URL}"
        )
        dernier_http = client
        emissions = _emissions(edge)
        serial_servi, details_certificat = _certificat_servi(edge)
        if client.rc == 0 and serial_servi:
            break
        time.sleep(5)

    assert dernier_http is not None and dernier_http.rc == 0, message(
        en=f"Traefik did not serve a trusted HTTPS response within "
        f"{DELAI_DEMARRAGE_S}s. Is the router and ACME resolver running?",
        fr=f"Traefik n'a pas servi de réponse HTTPS de confiance en "
        f"{DELAI_DEMARRAGE_S}s. Le routeur et le resolver ACME sont-ils actifs ?",
    )
    assert "Hostname:" in dernier_http.stdout, message(
        en=f"HTTPS did not return the expected whoami service response: "
        f"{dernier_http.stdout[:300]!r}.",
        fr=f"La réponse HTTPS ne correspond pas au service whoami attendu : "
        f"{dernier_http.stdout[:300]!r}.",
    )

    emissions_uniques = list(dict.fromkeys(emissions))
    assert emissions_uniques and serial_servi == emissions_uniques[-1], message(
        en="The initial certificate served by Traefik does not match a "
        f"certificate issued by the running Pebble authority: served="
        f"{serial_servi!r}, issued={emissions_uniques!r}.",
        fr="Le certificat initial servi par Traefik ne correspond pas à un "
        f"certificat émis par Pebble : servi={serial_servi!r}, "
        f"émis={emissions_uniques!r}.",
    )
    assert f"DNS:{HOTE}" in details_certificat, message(
        en=f"The certificate served by Traefik does not cover {HOTE}: "
        f"{details_certificat.strip()!r}.",
        fr=f"Le certificat servi par Traefik ne couvre pas {HOTE} : "
        f"{details_certificat.strip()!r}.",
    )

    echeance_renouvellement = time.monotonic() + DELAI_RENOUVELLEMENT_S
    while time.monotonic() < echeance_renouvellement:
        client = edge.run(
            f"curl --max-time 5 --silent --show-error --cacert {AUTORITE} "
            f"--resolve {HOTE}:443:127.0.0.1 {URL}"
        )
        dernier_http = client
        emissions = _emissions(edge)
        serial_servi, details_certificat = _certificat_servi(edge)
        emissions_uniques = list(dict.fromkeys(emissions))
        if (
            client.rc == 0
            and len(emissions_uniques) >= 2
            and serial_servi == emissions_uniques[-1]
            and f"DNS:{HOTE}" in details_certificat
        ):
            break
        time.sleep(5)

    emissions_uniques = list(dict.fromkeys(emissions))
    assert dernier_http is not None and dernier_http.rc == 0, message(
        en="An HTTPS client could not reach the service with Pebble's CA. "
        "Check the router, TLS certificate, and backend.",
        fr="Un client HTTPS n'a pas pu joindre le service avec la CA de Pebble. "
        "Vérifiez le routeur, le certificat TLS et le backend.",
    )
    assert "Hostname:" in dernier_http.stdout, message(
        en=f"HTTPS did not return the expected whoami service response: "
        f"{dernier_http.stdout[:300]!r}.",
        fr=f"La réponse HTTPS ne correspond pas au service whoami attendu : "
        f"{dernier_http.stdout[:300]!r}.",
    )
    assert len(emissions_uniques) >= 2, message(
        en=f"Pebble logged {len(emissions_uniques)} distinct certificate "
        f"issuance(s), not an initial issuance followed by an automatic renewal "
        f"within {DELAI_RENOUVELLEMENT_S}s.",
        fr=f"Pebble a journalisé {len(emissions_uniques)} émission(s) de "
        f"certificat distinctes, pas une émission initiale suivie d'un "
        f"renouvellement automatique en {DELAI_RENOUVELLEMENT_S}s.",
    )
    assert serial_servi == emissions_uniques[-1], message(
        en=f"Traefik serves serial {serial_servi!r}, but Pebble's latest "
        f"issued serial is {emissions_uniques[-1]!r}. Certificate details: "
        f"{details_certificat.strip()!r}.",
        fr=f"Traefik sert le numéro {serial_servi!r}, mais le dernier numéro "
        f"émis par Pebble est {emissions_uniques[-1]!r}. Détails : "
        f"{details_certificat.strip()!r}.",
    )
    assert f"DNS:{HOTE}" in details_certificat, message(
        en=f"The certificate served by Traefik does not cover {HOTE}: "
        f"{details_certificat.strip()!r}.",
        fr=f"Le certificat servi par Traefik ne couvre pas {HOTE} : "
        f"{details_certificat.strip()!r}.",
    )
