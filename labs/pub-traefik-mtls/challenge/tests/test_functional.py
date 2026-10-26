"""Verify client certificate enforcement, backend certificate verification,
resistance to forged forwarding headers, and survival of a certificate
rotation.

CE QUE LA VERSION PRÉCÉDENTE NE MESURAIT PAS, et pourquoi elle passait

Les quatre tests concluaient sur « un statut différent de 200 ». Or trois
situations sans rapport rendent toutes un statut différent de 200 :

  - un refus TLS, qui est le comportement cherché ;
  - un 404, qui dit que la route n'existe pas, donc que rien n'a été
    présenté au contrôle ;
  - un `000`, qui dit qu'aucune réponse n'est revenue, ce qui arrive aussi
    bien quand le service est éteint que quand curl ne sait pas lire le
    fichier de certificat qu'on lui donne.

Contre-test du 2026-10-25 : avec le backend invalide répondant **404**, le
test du backend passait au vert sans avoir démontré le moindre refus TLS.

LA CORRECTION : LIRE AUSSI LE CODE DE SORTIE DE CURL

Le code HTTP seul ne distingue pas ces cas, le code de sortie de curl si.
Chaque sonde rend donc les deux, et chaque assertion dit laquelle des trois
situations elle exige. Un test qui ne sait pas pourquoi il est vert n'est
pas vert.

POURQUOI `-k` RESTE, CONTRAIREMENT À CE QU'ON POURRAIT CROIRE

`-k` ne concerne que la validation, PAR CURL, du certificat de `edge.lab`.
Aucun test d'ici ne mesure cela : ce qui se mesure est le certificat CLIENT
qu'exige Traefik, et le certificat du BACKEND que Traefik doit vérifier.
Le certificat serveur posé par la fixture porte
`subjectAltName=DNS:mtls.lab.test` et rien d'autre, alors que les sondes
visent `bon.mtls.lab.test` et `mauvais.mtls.lab.test`. Le retirer ferait
donc rendre `000` aux quatre tests sur une simple non-correspondance de nom,
et l'on conclurait au refus mTLS en ayant mesuré un nom d'hôte.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
WORK = "/opt/pub-mtls"
CERTS = f"{WORK}/certs"

# Codes de sortie de curl, groupés par ce qu'ils PROUVENT.
#
# Un refus de certificat client se manifeste au niveau TLS : la poignée de
# main échoue, et curl sort sur une erreur de cette famille.
#
# Les deux autres familles ne prouvent rien sur mTLS, et doivent donc faire
# ÉCHOUER le test au lieu de le valider : c'est exactement ce que la version
# précédente faisait à l'envers.
CURL_CERT_LOCAL_ILLISIBLE = {58}        # fichier de certificat absent ou invalide
CURL_SERVICE_INJOIGNABLE = {6, 7, 28}   # DNS, connexion refusée, délai dépassé


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _sonde(edge, host: str, cert: str | None = None,
           extra_headers: str = "") -> tuple[str, int]:
    """Une requête vers le point d'entrée, rendue comme (code HTTP, code curl).

    Les deux sont nécessaires : le code HTTP dit ce que le serveur a répondu,
    le code de sortie dit s'il a répondu quelque chose.
    """
    cert_args = f"--cert {CERTS}/{cert}.crt --key {CERTS}/{cert}.key" if cert else ""
    res = edge.run(
        f"curl -k -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"--resolve {host}:8443:127.0.0.1 {cert_args} {extra_headers} "
        f"https://{host}:8443/"
    )
    return res.stdout.strip(), res.rc


def _pourquoi_ce_n_est_pas_un_refus_tls(nom: str, code: str, rc: int) -> str | None:
    """Rend None si c'en est bien un, sinon la raison en clair.

    Écrit en négatif à dessein : le test n'a pas à prouver qu'un refus a eu
    lieu en constatant l'absence de succès, il a à écarter une par une les
    autres causes possibles du même symptôme.
    """
    if code == "200":
        return f"{nom} a été ACCEPTÉ (HTTP 200)"
    if rc in CURL_CERT_LOCAL_ILLISIBLE:
        return (
            f"{nom} : curl n'a pas pu lire le fichier de certificat "
            f"(code {rc}). Rien n'a été présenté au serveur, donc rien n'a "
            "été mesuré"
        )
    if rc in CURL_SERVICE_INJOIGNABLE:
        return (
            f"{nom} : le service n'a pas répondu du tout (code curl {rc}). "
            "C'est une panne ou un port fermé, pas un refus de certificat"
        )
    if rc == 0:
        return (
            f"{nom} : la connexion TLS a ABOUTI et le serveur a répondu "
            f"HTTP {code}. C'est une réponse applicative, pas un refus au "
            "niveau TLS : le certificat client a donc été accepté"
        )
    return None


def test_client_certificat_requis_et_verifie(edge) -> None:
    """Un certificat client valide passe, les trois autres sont refusés AU NIVEAU TLS.

    Le cas valide sert d'ancrage : sans lui, un `000` partout voudrait dire
    « tout est refusé » aussi bien que « rien n'écoute », et on ne saurait
    pas lequel.
    """
    code_valide, rc_valide = _sonde(edge, "bon.mtls.lab.test", cert="client-valide")
    assert code_valide == "200" and rc_valide == 0, message(
        en=(
            "A client certificate signed by the lab's client CA must be accepted. "
            "Until it is, nothing can be concluded from the refusals: a listener "
            f"that is down refuses everything too (HTTP {code_valide!r}, curl "
            f"{rc_valide})."
        ),
        fr=(
            "Un certificat client signé par la CA client du lab doit être accepté. "
            "Tant qu'il ne l'est pas, les refus ne prouvent rien : un service "
            f"éteint refuse tout aussi bien (HTTP {code_valide!r}, curl "
            f"{rc_valide})."
        ),
    )

    desaccords = []
    for nom, cert in (
        ("sans certificat", None),
        ("certificat d'une CA étrangère", "client-etranger"),
        ("certificat expiré", "client-expire"),
    ):
        code, rc = _sonde(edge, "bon.mtls.lab.test", cert=cert)
        raison = _pourquoi_ce_n_est_pas_un_refus_tls(nom, code, rc)
        if raison:
            desaccords.append(raison)

    assert not desaccords, message(
        en=(
            "No certificate, a certificate from a foreign CA and an expired "
            "certificate must each be refused during the TLS handshake. Require "
            "and verify the client certificate against the lab's client CA. "
            + " ; ".join(desaccords)
        ),
        fr=(
            "Sans certificat, un certificat d'une CA étrangère et un certificat "
            "expiré doivent chacun être refusés pendant la poignée de main TLS. "
            "Exigez et vérifiez le certificat client contre la CA client du lab. "
            + " ; ".join(desaccords)
        ),
    )


def test_backend_tls_verifie_sans_desactiver_la_verification(edge) -> None:
    """Le backend au mauvais certificat fait répondre Traefik en 5xx, pas en 404.

    LE FAUX POSITIF QUE CE TEST CORRIGE. L'ancienne version acceptait « tout
    sauf 200 et 000 », donc un 404. Or un 404 dit que la route n'existe pas :
    la requête n'a jamais atteint le backend, et la vérification TLS amont
    n'a jamais eu l'occasion de refuser quoi que ce soit. Seul un 5xx prouve
    que Traefik a bien tenté la connexion amont et l'a rejetée.
    """
    code_bon, rc_bon = _sonde(edge, "bon.mtls.lab.test", cert="client-valide")
    assert code_bon == "200" and rc_bon == 0, message(
        en=(
            "The valid backend must still answer 200 once backend verification is "
            f"enabled. Verifying must not break what works (HTTP {code_bon!r})."
        ),
        fr=(
            "Le backend valide doit toujours répondre 200 une fois la vérification "
            "amont activée. Vérifier ne doit pas casser ce qui marche "
            f"(HTTP {code_bon!r})."
        ),
    )

    code_mauvais, rc_mauvais = _sonde(edge, "mauvais.mtls.lab.test", cert="client-valide")
    assert code_mauvais.startswith("5"), message(
        en=(
            "The backend presenting a certificate from an unrelated CA must make "
            "the upstream connection fail, which Traefik reports as a 5xx. "
            + (
                "A 404 means the route does not exist: the request never reached "
                "the backend, so backend verification was never exercised. "
                if code_mauvais == "404"
                else ""
            )
            + (
                "A 200 means verification is still disabled. "
                if code_mauvais == "200"
                else ""
            )
            + f"(HTTP {code_mauvais!r}, curl {rc_mauvais})."
        ),
        fr=(
            "Le backend présentant un certificat d'une CA sans rapport doit faire "
            "échouer la connexion amont, ce que Traefik rend par un 5xx. "
            + (
                "Un 404 signifie que la route n'existe pas : la requête n'a jamais "
                "atteint le backend, et la vérification amont n'a donc jamais été "
                "mise à l'épreuve. "
                if code_mauvais == "404"
                else ""
            )
            + (
                "Un 200 signifie que la vérification est toujours désactivée. "
                if code_mauvais == "200"
                else ""
            )
            + f"(HTTP {code_mauvais!r}, curl {rc_mauvais})."
        ),
    )


def test_origine_resiste_aux_en_tetes_forges(edge) -> None:
    """Un X-Forwarded-For forgé n'atteint pas le backend, celui du proxy amont si.

    LE FAUX POSITIF QUE CE TEST CORRIGE. L'ancienne version se contentait de
    `forge not in direct.stdout`, qui est VRAI quand la sortie est vide. Une
    requête entièrement ratée validait donc le test. On exige d'abord que la
    requête aboutisse et atteigne le backend, et seulement ensuite que
    l'adresse forgée en soit absente.
    """
    forge = "203.0.113.9"
    direct = edge.run(
        "curl -k -s --max-time 5 --resolve bon.mtls.lab.test:8443:127.0.0.1 "
        f"--cert {CERTS}/client-valide.crt --key {CERTS}/client-valide.key "
        f"-H 'X-Forwarded-For: {forge}' https://bon.mtls.lab.test:8443/"
    )
    assert direct.rc == 0 and "Hostname: backend-bon" in direct.stdout, message(
        en=(
            "The direct request must reach the backend before anything can be said "
            "about the header it carried: an empty answer contains no forged "
            "address either, and would pass for a success. "
            f"(curl {direct.rc}, body {direct.stdout.strip()[:120]!r})."
        ),
        fr=(
            "La requête directe doit atteindre le backend avant qu'on puisse rien "
            "dire de l'en-tête qu'elle portait : une réponse vide ne contient pas "
            "davantage l'adresse forgée, et passerait pour un succès. "
            f"(curl {direct.rc}, corps {direct.stdout.strip()[:120]!r})."
        ),
    )
    assert forge not in direct.stdout, message(
        en=(
            f"The forged X-Forwarded-For ({forge}) reached the backend unchanged. "
            "Scope forwardedHeaders.trustedIPs to the upstream proxy's address "
            "only, so that a direct and untrusted caller cannot choose its own "
            "identity."
        ),
        fr=(
            f"Le X-Forwarded-For forgé ({forge}) a atteint le backend tel quel. "
            "Restreignez forwardedHeaders.trustedIPs à la seule adresse du proxy "
            "amont, pour qu'un appelant direct et non fiable ne choisisse pas son "
            "identité."
        ),
    )

    via_amont = edge.run(
        "curl -s --max-time 5 -H 'Host: bon.mtls.lab.test' "
        f"-H 'X-Forwarded-For: {forge}' http://127.0.0.1:8080/"
    )
    assert "Hostname: backend-bon" in via_amont.stdout, message(
        en=(
            "A request relayed by the lab's authorized upstream proxy must still "
            "reach the backend. Refusing everyone is not scoping trust: it is "
            f"removing the proxy (body {via_amont.stdout.strip()[:120]!r})."
        ),
        fr=(
            "Une requête relayée par le proxy amont autorisé du lab doit toujours "
            "atteindre le backend. Refuser tout le monde n'est pas restreindre la "
            f"confiance, c'est supprimer le proxy (corps "
            f"{via_amont.stdout.strip()[:120]!r})."
        ),
    )


def test_rotation_remplacement_certificats_conserve_le_controle(edge) -> None:
    """Après rotation, la nouvelle CA passe, l'ancienne est refusée AU NIVEAU TLS.

    La CA client est un fichier partagé et persistant sur la cible : ce test
    la remplace pour vérifier la rotation, puis DOIT la restaurer à
    l'identique. Sans cette restauration, la mutation survit au test (la
    cible garde son état entre les invocations de pytest) et casse le
    premier test de la pose de solution suivante, qui s'attend à retrouver la
    CA d'origine en face du certificat `client-valide` signé avec elle.
    """
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

        code_nouveau, rc_nouveau = _sonde(
            edge, "bon.mtls.lab.test", cert="client-rotation"
        )
        assert code_nouveau == "200" and rc_nouveau == 0, message(
            en=(
                "After rotating the client CA, a certificate signed by the NEW CA "
                "must be accepted. A rotation that locks everyone out is an outage, "
                f"not a rotation (HTTP {code_nouveau!r}, curl {rc_nouveau})."
            ),
            fr=(
                "Après rotation de la CA client, un certificat signé par la "
                "NOUVELLE CA doit être accepté. Une rotation qui met tout le monde "
                f"dehors est une panne, pas une rotation (HTTP {code_nouveau!r}, "
                f"curl {rc_nouveau})."
            ),
        )

        desaccords = []
        for nom, cert in (
            ("certificat signé par la CA remplacée", "client-valide"),
            ("certificat d'une CA étrangère", "client-etranger"),
        ):
            code, rc = _sonde(edge, "bon.mtls.lab.test", cert=cert)
            raison = _pourquoi_ce_n_est_pas_un_refus_tls(nom, code, rc)
            if raison:
                desaccords.append(raison)

        assert not desaccords, message(
            en=(
                "Once the CA is rotated, a certificate signed by the replaced CA "
                "must be refused during the handshake, and an unrelated one must "
                "stay refused. A rotation that keeps honouring the old CA has not "
                "revoked anything. " + " ; ".join(desaccords)
            ),
            fr=(
                "Une fois la CA tournée, un certificat signé par la CA remplacée "
                "doit être refusé pendant la poignée de main, et un certificat sans "
                "rapport doit le rester. Une rotation qui continue d'honorer "
                "l'ancienne CA n'a rien révoqué. " + " ; ".join(desaccords)
            ),
        )
    finally:
        edge.run(f"cp {CERTS}/client-ca-originale.crt {CERTS}/client-ca.crt")
        edge.run(
            f"echo '# rotation-restauree-{int(time.time())}' >> {WORK}/dynamic/routes.yaml"
        )
        time.sleep(2)
