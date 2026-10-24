"""Verify Pebble issuance, renewal, TLS, and uninterrupted HAProxy service."""

from __future__ import annotations

import re
import socket
import ssl
import threading
import time

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
IP_CIBLE = lab_host_ip(CIBLE)
HOTE = "app.lab.test"
CA = "/opt/pub-traefik-acme/pebble-root.pem"
CONTENEUR = "pub-haproxy-tls"


def _edge():
    return lab_host(CIBLE)


def _serial_servi(edge) -> str | None:
    result = edge.run(
        f"timeout 8 openssl s_client -connect 127.0.0.1:443 "
        f"-servername {HOTE} </dev/null 2>/dev/null | "
        "openssl x509 -noout -serial -ext subjectAltName"
    )
    if result.rc != 0 or f"DNS:{HOTE}" not in result.stdout:
        return None
    match = re.search(r"^serial=([0-9a-fA-F]+)$", result.stdout, re.M)
    return match.group(1).lower().lstrip("0") if match else None


def _serials_emis(edge) -> list[str]:
    journal = edge.run("docker logs pub-renewal-pebble 2>&1")
    return [
        value.lower().lstrip("0")
        for value in re.findall(
            r"Issued certificate serial ([0-9a-fA-F]+)", journal.stdout
        )
    ]


def _attendre_certificat_pebble(edge, delai: int = 45) -> bool:
    echeance = time.monotonic() + delai
    while time.monotonic() < echeance:
        serial = _serial_servi(edge)
        if serial and serial in _serials_emis(edge):
            return True
        certificat_initial = edge.run(
            "timeout 8 openssl s_client -connect 127.0.0.1:443 "
            f"-servername {HOTE} </dev/null 2>/dev/null | "
            "openssl x509 -noout -ext subjectAltName"
        )
        if "DNS:wrong.lab.test" in certificat_initial.stdout:
            return False
        time.sleep(2)
    return False


def _requete_tls(ca_pem: str) -> str:
    context = ssl.create_default_context(cadata=ca_pem)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with (
        socket.create_connection((IP_CIBLE, 443), timeout=4) as raw,
        context.wrap_socket(raw, server_hostname=HOTE) as tls,
    ):
        tls.sendall(
            f"GET / HTTP/1.1\r\nHost: {HOTE}\r\nConnection: close\r\n\r\n".encode()
        )
        response = tls.recv(4096).split(b"\r\n", 1)[0].decode()
    return response


def test_http_redirige_et_https_publie_le_backend() -> None:
    edge = _edge()
    certificat_pret = _attendre_certificat_pebble(edge)
    http = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--write-out '%{http_code} %{redirect_url}' "
        f"--resolve {HOTE}:80:127.0.0.1 http://{HOTE}/"
    )
    https = edge.run(
        f"curl --max-time 5 --silent --show-error --cacert {CA} "
        f"--resolve {HOTE}:443:127.0.0.1 https://{HOTE}/"
    )
    assert (
        certificat_pret
        and http.rc == 0
        and http.stdout.strip().startswith(f"301 https://{HOTE}/")
        and https.rc == 0
        and "HAProxy backend" in https.stdout
    ), message(
        en="HTTP must redirect permanently to HTTPS, which must serve the "
        "expected backend.",
        fr="HTTP doit rediriger de façon permanente vers HTTPS, qui doit "
        "publier le backend attendu.",
    )


def test_certificat_servi_est_emis_par_pebble_et_correspond_au_sni() -> None:
    edge = _edge()
    assert _attendre_certificat_pebble(edge), message(
        en="HAProxy has not received a certificate from Pebble yet.",
        fr="HAProxy n'a pas encore reçu de certificat de Pebble.",
    )
    serial = _serial_servi(edge)
    issued = _serials_emis(edge)
    assert serial is not None and serial in issued, message(
        en="The certificate served for app.lab.test must cover that hostname "
        "and match a certificate issued by the running Pebble authority.",
        fr="Le certificat servi pour app.lab.test doit couvrir ce nom et "
        "correspondre à une émission de l'autorité Pebble active.",
    )


def test_cle_acme_et_versions_tls_sont_durcies() -> None:
    edge = _edge()
    assert _attendre_certificat_pebble(edge), message(
        en="HAProxy has not received a certificate from Pebble yet.",
        fr="HAProxy n'a pas encore reçu de certificat de Pebble.",
    )
    key_mode = edge.run("stat -c '%a' /opt/pub-haproxy-tls/account.key")
    moderne = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        f"--tlsv1.2 --tls-max 1.2 --cacert {CA} "
        f"--resolve {HOTE}:443:127.0.0.1 https://{HOTE}/"
    )
    obsolete = {
        version: edge.run(
            "curl --max-time 5 --silent --show-error --output /dev/null "
            f"--tlsv{version} --tls-max {version} --insecure "
            f"--resolve {HOTE}:443:127.0.0.1 https://{HOTE}/"
        )
        for version in ("1.0", "1.1")
    }
    accepts_obsolete = [
        version for version, result in obsolete.items() if result.rc == 0
    ]
    assert (
        key_mode.rc == 0
        and key_mode.stdout.strip() == "600"
        and moderne.rc == 0
        and not accepts_obsolete
    ), message(
        en=f"The ACME account key must be mode 0600, TLS 1.2 must work, and "
        f"TLS 1.0/1.1 must be rejected (accepted: {accepts_obsolete}).",
        fr=f"La clé ACME doit être en mode 0600, TLS 1.2 doit fonctionner et "
        f"TLS 1.0/1.1 doivent être refusés (acceptés : {accepts_obsolete}).",
    )


def test_renouvellement_est_servi_sans_redemarrer_ni_couper_le_service() -> None:
    edge = _edge()
    assert _attendre_certificat_pebble(edge), message(
        en="HAProxy has not received a certificate from Pebble yet.",
        fr="HAProxy n'a pas encore reçu de certificat de Pebble.",
    )
    initial = _serial_servi(edge)
    authority = edge.run(f"cat {CA}")
    started = edge.run(
        f"docker inspect --format '{{{{.State.StartedAt}}}}' {CONTENEUR}"
    )
    assert (
        initial is not None
        and authority.rc == 0
        and started.rc == 0
    ), message(
        en="An initial Pebble certificate and running HAProxy container are "
        "required before renewal can be assessed.",
        fr="Un certificat Pebble initial et un conteneur HAProxy actif sont "
        "nécessaires pour évaluer le renouvellement.",
    )

    commandes: list[str] = []
    erreurs: list[str] = []
    stop = threading.Event()

    def surveiller_service() -> None:
        while not stop.is_set():
            try:
                commandes.append(_requete_tls(authority.stdout))
            except (OSError, ssl.SSLError) as erreur:
                erreurs.append(type(erreur).__name__)
            time.sleep(0.1)

    worker = threading.Thread(target=surveiller_service, daemon=True)
    worker.start()
    time.sleep(0.3)
    renewal = edge.run(
        "sudo python3 -c 'import socket; "
        "s=socket.socket(socket.AF_UNIX); s.settimeout(10); "
        "s.connect(\"/opt/pub-haproxy-tls/run/admin.sock\"); "
        "s.sendall(b\"acme renew @haproxy-certs/app.lab.test.pem\\n\"); "
        "s.shutdown(socket.SHUT_WR); "
        "print(s.recv(4096).decode())'"
    )

    deadline = time.monotonic() + 45
    renewed = None
    issued: list[str] = []
    while time.monotonic() < deadline:
        renewed = _serial_servi(edge)
        issued = _serials_emis(edge)
        if renewed and renewed != initial and renewed in issued:
            break
        time.sleep(1)
    stop.set()
    worker.join(timeout=5)
    finished = edge.run(
        f"docker inspect --format '{{{{.State.StartedAt}}}}' {CONTENEUR}"
    )
    final_response = edge.run(
        f"curl --max-time 5 --silent --show-error --cacert {CA} "
        f"--resolve {HOTE}:443:127.0.0.1 --output /dev/null "
        f"--write-out '%{{http_code}}' https://{HOTE}/"
    )
    assert (
        renewal.rc == 0
        and "Can't find the certificate" not in renewal.stdout
        and renewed is not None
        and renewed != initial
        and renewed in issued
        and finished.rc == 0
        and finished.stdout.strip() == started.stdout.strip()
        and final_response.rc == 0
        and final_response.stdout.strip() == "200"
        and commandes
        and all(
            len(response.split()) > 1 and response.split()[1] == "200"
            for response in commandes
        )
        and not erreurs
    ), message(
        en="HAProxy must serve a new Pebble-issued certificate after the ACME "
        "renewal command, keep the same container start time, and return HTTP "
        "200 for every request observed during renewal.",
        fr="HAProxy doit servir un nouveau certificat Pebble après la commande "
        "de renouvellement ACME, conserver son heure de démarrage et répondre "
        "HTTP 200 à chaque requête observée pendant le renouvellement.",
    )
