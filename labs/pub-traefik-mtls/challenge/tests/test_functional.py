"""Verify client certificate enforcement, backend certificate verification,
resistance to forged forwarding headers, and survival of a certificate
rotation."""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
WORK = "/opt/pub-mtls"
CERTS = f"{WORK}/certs"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _curl_direct(edge, host: str, cert: str | None = None, key: str | None = None,
                  extra_headers: str = "") -> object:
    cert_args = f"--cert {CERTS}/{cert}.crt --key {CERTS}/{cert}.key" if cert else ""
    return edge.run(
        f"curl -k -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"--resolve {host}:8443:127.0.0.1 {cert_args} {extra_headers} "
        f"https://{host}:8443/"
    )


def test_client_certificat_requis_et_verifie(edge) -> None:
    valide = _curl_direct(edge, "bon.mtls.lab.test", cert="client-valide")
    sans_cert = _curl_direct(edge, "bon.mtls.lab.test")
    etranger = _curl_direct(edge, "bon.mtls.lab.test", cert="client-etranger")
    expire = _curl_direct(edge, "bon.mtls.lab.test", cert="client-expire")
    assert (
        valide.stdout == "200"
        and sans_cert.stdout != "200"
        and etranger.stdout != "200"
        and expire.stdout != "200"
    ), message(
        en="A client certificate signed by the lab's client CA must be "
        "accepted; no certificate, a certificate from a foreign CA, or an "
        "expired certificate must all be refused. Require and verify the "
        f"client certificate (valid: {valide.stdout!r}, none: "
        f"{sans_cert.stdout!r}, foreign: {etranger.stdout!r}, expired: "
        f"{expire.stdout!r}).",
        fr="Un certificat client signé par la CA client du lab doit être "
        "accepté ; sans certificat, un certificat d'une CA étrangère ou un "
        "certificat expiré doivent tous être refusés. Exigez et vérifiez le "
        f"certificat client (valide : {valide.stdout!r}, absent : "
        f"{sans_cert.stdout!r}, étranger : {etranger.stdout!r}, expiré : "
        f"{expire.stdout!r}).",
    )


def test_backend_tls_verifie_sans_desactiver_la_verification(edge) -> None:
    bon = _curl_direct(edge, "bon.mtls.lab.test", cert="client-valide")
    mauvais = _curl_direct(edge, "mauvais.mtls.lab.test", cert="client-valide")
    assert (
        bon.stdout == "200" and mauvais.stdout not in ("200", "000")
    ), message(
        en="The valid backend must work and the backend presenting a "
        "certificate from an unrelated CA must make the upstream "
        "connection fail (a 5xx from Traefik), without disabling backend "
        f"TLS verification (bon: {bon.stdout!r}, mauvais: {mauvais.stdout!r}).",
        fr="Le backend valide doit fonctionner et le backend présentant un "
        "certificat d'une CA sans rapport doit faire échouer la connexion "
        "amont (un 5xx renvoyé par Traefik), sans désactiver la "
        f"vérification TLS du backend (bon : {bon.stdout!r}, mauvais : "
        f"{mauvais.stdout!r}).",
    )


def test_origine_resiste_aux_en_tetes_forges(edge) -> None:
    forge = "203.0.113.9"
    direct = edge.run(
        "curl -k -s --max-time 5 --resolve bon.mtls.lab.test:8443:127.0.0.1 "
        f"--cert {CERTS}/client-valide.crt --key {CERTS}/client-valide.key "
        f"-H 'X-Forwarded-For: {forge}' https://bon.mtls.lab.test:8443/"
    )
    via_amont = edge.run(
        "curl -s --max-time 5 -H 'Host: bon.mtls.lab.test' "
        f"-H 'X-Forwarded-For: {forge}' http://127.0.0.1:8080/"
    )
    assert (
        forge not in direct.stdout and "Hostname: backend-bon" in via_amont.stdout
    ), message(
        en="A forged X-Forwarded-For sent directly by an untrusted caller "
        "must not reach the backend unchanged; a request relayed by the "
        "lab's authorized upstream proxy must still reach the backend. "
        "Scope forwardedHeaders.trustedIPs to the upstream proxy's address "
        f"only (direct: {direct.stdout!r}).",
        fr="Un X-Forwarded-For forgé envoyé directement par un appelant non "
        "fiable ne doit pas atteindre le backend tel quel ; une requête "
        "relayée par le reverse proxy amont autorisé du lab doit toujours "
        "atteindre le backend. Restreignez forwardedHeaders.trustedIPs à la "
        f"seule adresse du proxy amont (direct : {direct.stdout!r}).",
    )


def test_rotation_remplacement_certificats_conserve_le_controle(edge) -> None:
    # La CA client est un fichier partagé et persistant sur la cible : ce
    # test la remplace pour vérifier la rotation, puis DOIT la restaurer à
    # l'identique. Sans cette restauration, la mutation survit au test (la
    # cible garde son état entre les invocations de pytest) et casse le
    # test_client... de la pose de solution suivante, qui s'attend à
    # retrouver la CA d'origine en face du certificat client-valide signé
    # avec elle.
    edge.run(f"cp {CERTS}/client-ca.crt {CERTS}/client-ca-originale.crt")
    try:
        edge.run(
            f"openssl genrsa -out {CERTS}/client-ca-v2.key 2048 && "
            f"openssl req -x509 -new -nodes -key {CERTS}/client-ca-v2.key "
            "-sha256 -days 30 -subj '/CN=pub-mtls Client CA v2' "
            f"-out {CERTS}/client-ca-v2.crt && "
            f"openssl genrsa -out {CERTS}/client-rotation.key 2048 && "
            f"openssl req -new -key {CERTS}/client-rotation.key "
            "-subj '/CN=client-rotation' "
            f"-out {CERTS}/client-rotation.csr && "
            f"openssl x509 -req -in {CERTS}/client-rotation.csr "
            f"-CA {CERTS}/client-ca-v2.crt -CAkey {CERTS}/client-ca-v2.key "
            f"-CAcreateserial -days 30 -sha256 -out {CERTS}/client-rotation.crt"
        )
        edge.run(f"cp {CERTS}/client-ca-v2.crt {CERTS}/client-ca.crt")
        # Le provider fichier de Traefik ne surveille que le répertoire
        # dynamique : une modification du fichier de routes force une
        # relecture qui recharge aussi les fichiers de certificats
        # référencés par chemin.
        edge.run(f"echo '# rotation-{int(time.time())}' >> {WORK}/dynamic/routes.yaml")
        time.sleep(4)

        nouveau = _curl_direct(edge, "bon.mtls.lab.test", cert="client-rotation")
        ancien = _curl_direct(edge, "bon.mtls.lab.test", cert="client-valide")
        toujours_invalide = _curl_direct(edge, "bon.mtls.lab.test", cert="client-etranger")

        assert (
            nouveau.stdout == "200"
            and ancien.stdout != "200"
            and toujours_invalide.stdout != "200"
        ), message(
            en="After rotating the client CA, a certificate signed by the "
            "new CA must be accepted, a certificate signed by the replaced "
            "CA must now be refused, and an unrelated certificate must "
            f"still be refused (new: {nouveau.stdout!r}, old: "
            f"{ancien.stdout!r}, foreign: {toujours_invalide.stdout!r}).",
            fr="Après rotation de la CA client, un certificat signé par la "
            "nouvelle CA doit être accepté, un certificat signé par la CA "
            "remplacée doit désormais être refusé, et un certificat sans "
            f"rapport doit rester refusé (nouveau : {nouveau.stdout!r}, "
            f"ancien : {ancien.stdout!r}, étranger : "
            f"{toujours_invalide.stdout!r}).",
        )
    finally:
        edge.run(f"cp {CERTS}/client-ca-originale.crt {CERTS}/client-ca.crt")
        edge.run(
            f"echo '# rotation-restauree-{int(time.time())}' >> {WORK}/dynamic/routes.yaml"
        )
        time.sleep(2)
