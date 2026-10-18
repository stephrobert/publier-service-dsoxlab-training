"""L'état de Pebble et du certificat, interrogés tels qu'un client les voit.

Aucun test ne lit le Compose de l'apprenant ni ne cherche une commande lego.
Ils interrogent Pebble (annuaire sur 14000, gestion sur 15000) et le
certificat. Quatre preuves, dans l'ordre où elles se déduisent :

1. Pebble répond, et sa racine courante est récupérable sur :15000 ;
2. le certificat existe, chaîne vers CETTE racine (Pebble en génère une neuve à
   chaque démarrage : un certificat d'un essai précédent ne vérifie pas), vaut
   pour app.lab.test et n'est pas expiré ;
3. la clé privée est celle du certificat ;
4. la validation a eu lieu : le journal de Pebble porte le défi complété, et
   le numéro de série du certificat y figure à la ligne « Issued certificate ».

Mesuré le 2026-10-18 (Pebble 2.10.1, lego v5.5.2) : lego, lancé dans un
conteneur, écrit ses fichiers en root, d'où le `sudo` des lectures (la fixture
testinfra l'active).
"""

from __future__ import annotations

import re

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")

DOSSIER = "/opt/pub-lab/lego/certificates"
NOM = "app.lab.test"
CERT = f"{DOSSIER}/{NOM}.crt"
CLE = f"{DOSSIER}/{NOM}.key"
GESTION = "https://localhost:15000"
ANNUAIRE = "https://localhost:14000/dir"
TMP = "/tmp/pub01-verif"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _journal_pebble(hote) -> str:
    """Le journal du conteneur Pebble (pas celui de pebble-challtestsrv)."""
    res = hote.run(
        "for c in $(docker ps -q); do "
        "img=$(docker inspect -f '{{.Config.Image}}' $c); "
        "case \"$img\" in ghcr.io/letsencrypt/pebble:*|ghcr.io/letsencrypt/pebble@*) "
        "docker logs $c 2>&1;; esac; done"
    )
    return res.stdout


def test_pebble_repond_sur_annuaire_et_gestion(edge) -> None:
    for url in (ANNUAIRE, f"{GESTION}/roots/0"):
        res = edge.run(f"curl -sk -o /dev/null -w '%{{http_code}}' {url}")
        assert res.stdout.strip() == "200", message(
            en=f"{url} does not answer 200 (got {res.stdout.strip()!r}). Is "
            "Pebble running, with 14000 and 15000 published on localhost?",
            fr=f"{url} ne répond pas 200 (reçu {res.stdout.strip()!r}). Pebble "
            "tourne-t-il, avec 14000 et 15000 publiés sur localhost ?",
        )


def test_certificat_present(edge) -> None:
    f = edge.file(CERT)
    assert f.exists and f.size > 0, message(
        en=f"{CERT} is missing. lego writes under the --path directory, in "
        "certificates/. Check the path you gave it.",
        fr=f"{CERT} est absent. lego écrit sous le dossier de --path, dans "
        "certificates/. Vérifiez le chemin que vous lui avez donné.",
    )


@pytest.fixture(scope="module")
def chaine(edge) -> str:
    """Racine et intermédiaire COURANTS de Pebble, rangés dans un dossier de travail."""
    res = edge.run(
        f"rm -rf {TMP} && mkdir -p {TMP} && "
        f"curl -sk {GESTION}/roots/0 -o {TMP}/root.pem && "
        f"curl -sk {GESTION}/intermediates/0 -o {TMP}/inter.pem"
    )
    assert res.rc == 0, message(
        en="Pebble's management API (:15000) does not give its root.",
        fr="L'API de gestion de Pebble (:15000) ne donne pas sa racine.",
    )
    return TMP


def test_certificat_emis_par_la_racine_courante_de_pebble(edge, chaine) -> None:
    res = edge.run(
        f"openssl verify -CAfile {chaine}/root.pem -untrusted {chaine}/inter.pem {CERT}"
    )
    assert res.rc == 0 and res.stdout.strip().endswith(": OK"), message(
        en="The certificate does not verify against the root Pebble serves "
        f"now ({(res.stdout + res.stderr).strip()}). Pebble creates a new root "
        "at every start: a certificate from an earlier run is useless. Obtain "
        "it again from the running Pebble.",
        fr="Le certificat ne se vérifie pas contre la racine que Pebble sert "
        f"maintenant ({(res.stdout + res.stderr).strip()}). Pebble crée une "
        "racine neuve à chaque démarrage : un certificat d'un essai antérieur "
        "ne sert à rien. Obtenez-le de nouveau auprès du Pebble qui tourne.",
    )


def test_certificat_pour_le_bon_nom(edge) -> None:
    res = edge.run(f"openssl x509 -in {CERT} -noout -ext subjectAltName")
    assert f"DNS:{NOM}" in res.stdout, message(
        en=f"The certificate does not name {NOM} in its subjectAltName "
        f"(got: {res.stdout.strip()!r}).",
        fr=f"Le certificat ne nomme pas {NOM} dans son subjectAltName "
        f"(reçu : {res.stdout.strip()!r}).",
    )


def test_certificat_non_expire(edge) -> None:
    res = edge.run(f"openssl x509 -in {CERT} -noout -checkend 3600")
    assert res.rc == 0, message(
        en="The certificate expires within the hour or is already expired.",
        fr="Le certificat expire dans l'heure ou est déjà expiré.",
    )


def test_cle_privee_correspond_au_certificat(edge) -> None:
    pub_cert = edge.run(f"openssl x509 -in {CERT} -noout -pubkey")
    pub_cle = edge.run(f"openssl pkey -in {CLE} -pubout")
    assert pub_cert.rc == 0 and pub_cle.rc == 0 and pub_cert.stdout == pub_cle.stdout, message(
        en=f"{CLE} is missing or is not the private key of the certificate.",
        fr=f"{CLE} est absent ou n'est pas la clé privée du certificat.",
    )


def test_defi_http01_visible_dans_le_journal_de_pebble(edge) -> None:
    journal = _journal_pebble(edge)
    assert "set VALID by completed challenge" in journal, message(
        en="Pebble's log shows no completed challenge. Either Pebble runs in "
        "an 'always valid' mode, or this is not the Pebble that issued the "
        "certificate.",
        fr="Le journal de Pebble ne montre aucun défi complété. Soit Pebble "
        "tourne en mode « toujours valide », soit ce n'est pas le Pebble qui "
        "a émis le certificat.",
    )
    assert f"http://{NOM}:5002/.well-known/acme-challenge/" in journal, message(
        en=f"Pebble never tried http://{NOM}:5002/.well-known/acme-challenge/. "
        "The HTTP-01 challenge did not go through port 5002.",
        fr=f"Pebble n'a jamais appelé http://{NOM}:5002/.well-known/acme-challenge/. "
        "Le défi HTTP-01 n'est pas passé par le port 5002.",
    )


def test_numero_de_serie_du_certificat_dans_le_journal(edge) -> None:
    res = edge.run(f"openssl x509 -in {CERT} -noout -serial")
    m = re.search(r"serial=([0-9A-Fa-f]+)", res.stdout)
    assert m, message(en="Cannot read the certificate serial.", fr="Numéro de série illisible.")
    serie = m.group(1).lower().lstrip("0")
    assert f"Issued certificate serial {serie}" in _journal_pebble(edge), message(
        en=f"Serial {serie} is not in the 'Issued certificate' lines of the "
        "running Pebble's log: this certificate was not issued by it.",
        fr=f"Le numéro de série {serie} n'est pas dans les lignes « Issued "
        "certificate » du journal du Pebble en cours : il ne l'a pas émis.",
    )
