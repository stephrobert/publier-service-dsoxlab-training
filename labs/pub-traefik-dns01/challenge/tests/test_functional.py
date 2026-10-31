"""Tests fonctionnels du lab pub-traefik-dns01.

Ce qui est jugé, et d'où on le lit :

  - le certificat SERVI à un nom tiré au hasard sous boutique.lab.test, lu par
    une poignée de main TLS sous vérification stricte : un certificat par nom
    ne passe pas, seul un joker répond à un nom que personne n'a prévu ;
  - le JOURNAL du fournisseur DNS, qui dit quel compte a posé quel TXT : on ne
    lit pas la configuration de l'apprenant, on lit ce qui s'est passé ;
  - l'EMPREINTE de la plateforme posée par le banc, pour qu'une autorité
    affaiblie (qui validerait sans regarder le DNS) ne fasse pas passer le lab.

Chaque test exige d'abord qu'un joker ait été émis : avant le travail, rien
n'est vrai, et la suite vaut 0.
"""

from __future__ import annotations

import base64
import json
import secrets
import shlex

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
ZONE = "boutique.lab.test"
DEFI = f"_acme-challenge.{ZONE}"
JOURNAL = "/var/log/pub-traefik-dns01-fournisseur.jsonl"
COMPTES = "/etc/pub-traefik-dns01/comptes.json"
EMPREINTES = "/root/.pub-traefik-dns01-plateforme.sha256"
RACINE = "/tmp/pub-traefik-dns01-racine.pem"
FOURNISSEUR = "http://127.0.0.1:8060"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _journal(edge) -> list[dict]:
    lignes = edge.run(f"sudo cat {JOURNAL}").stdout.splitlines()
    entrees = []
    for ligne in lignes:
        try:
            entrees.append(json.loads(ligne))
        except ValueError:
            continue
    return entrees


def _comptes(edge) -> dict:
    try:
        return json.loads(edge.run(f"sudo cat {COMPTES}").stdout)
    except ValueError:
        return {}


def _racine(edge) -> str:
    res = edge.run(f"curl -sk --max-time 8 https://localhost:15000/roots/0 -o {RACINE} -w '%{{http_code}}'")
    assert res.stdout.strip() == "200", message(
        en="The test authority does not answer on localhost:15000: the platform is "
        "down, not your configuration.",
        fr="L'autorité de test ne répond pas sur localhost:15000 : c'est la "
        "plateforme qui est à terre, pas votre configuration.",
    )
    return RACINE


def _certificat_servi(edge, nom: str) -> dict[str, str]:
    """Sujet, émetteur et noms alternatifs du certificat présenté pour `nom`."""
    sortie = edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} 2>/dev/null "
        "| openssl x509 -noout -subject -issuer -ext subjectAltName 2>/dev/null"
    ).stdout
    return {"brut": sortie}


def _exiger_joker(edge) -> str:
    """Prémisse commune : un nom imprévu reçoit le joker, sous TLS strict."""
    racine = _racine(edge)
    nom = f"n{secrets.token_hex(4)}.{ZONE}"
    res = edge.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 --cacert {racine} "
        f"--resolve {nom}:443:127.0.0.1 https://{nom}/"
    )
    servi = _certificat_servi(edge, nom)["brut"]
    assert res.stdout.strip() == "200" and f"DNS:*.{ZONE}" in servi, message(
        en=f"https://{nom}/ (a name drawn at random) answers {res.stdout.strip() or res.rc} "
        f"under strict TLS, with this certificate: {servi.strip()[:240]!r}. Expected 200 "
        f"and a wildcard *.{ZONE} issued by the test authority.",
        fr=f"https://{nom}/ (un nom tiré au hasard) répond {res.stdout.strip() or res.rc} "
        f"sous TLS strict, avec ce certificat : {servi.strip()[:240]!r}. Attendu : 200 et "
        f"un joker *.{ZONE} émis par l'autorité de test.",
    )
    return nom


def _poses_reussies(edge) -> list[dict]:
    return [
        e for e in _journal(edge)
        if e.get("op") == "/present" and e.get("statut") == 200 and e.get("fqdn") == DEFI
    ]


def test_01_un_joker_est_servi_a_tout_nom_de_la_zone(edge) -> None:
    """Deux noms imprévus reçoivent le même joker, émis par DNS-01."""
    premier = _exiger_joker(edge)
    second = _exiger_joker(edge)
    assert premier != second
    assert _poses_reussies(edge), message(
        en=f"A wildcard is served, but the DNS provider never published {DEFI}: "
        "the certificate was not obtained through the DNS-01 challenge of this lab.",
        fr=f"Un joker est servi, mais le fournisseur DNS n'a jamais publié {DEFI} : "
        "le certificat n'a pas été obtenu par le défi DNS-01 de ce lab.",
    )


def test_02_l_automatisation_n_a_que_sa_zone(edge) -> None:
    """Le compte qui a publié le défi est limité à boutique.lab.test, et le prouve.

    Le compte admin a toutes les zones : confié à Traefik, il donnerait à
    quiconque lit sa configuration le pouvoir de réécrire tout le DNS. Le test
    retrouve dans le journal le compte réellement utilisé, puis lui fait
    tenter une publication hors de sa zone, qui doit être refusée.
    """
    _exiger_joker(edge)
    poses = _poses_reussies(edge)
    assert poses, message(
        en=f"No successful publication of {DEFI} in the provider's journal.",
        fr=f"Aucune publication réussie de {DEFI} dans le journal du fournisseur.",
    )
    utilises = sorted({e["compte"] for e in poses})
    assert "admin" not in utilises, message(
        en="The DNS-01 challenge was published with the admin account, which holds "
        "every zone. Give the automation an account limited to its own zone.",
        fr="Le défi DNS-01 a été publié avec le compte admin, qui détient toutes les "
        "zones. Donnez à l'automatisation un compte limité à sa propre zone.",
    )
    comptes = _comptes(edge)
    for nom in utilises:
        zones = comptes.get(nom, {}).get("zones")
        assert zones == [ZONE], message(
            en=f"Account {nom!r} holds the zones {zones}, not exactly [{ZONE!r}].",
            fr=f"Le compte {nom!r} détient les zones {zones}, et non exactement "
            f"[{ZONE!r}].",
        )
        jeton = base64.b64encode(f"{nom}:{comptes[nom]['mdp']}".encode()).decode()
        corps = json.dumps({"fqdn": "_acme-challenge.compta.lab.test.", "value": "intrus"})
        res = edge.run(
            "curl -s -o /dev/null -w '%{http_code}' --max-time 5 -X POST "
            f"-H {shlex.quote('Authorization: Basic ' + jeton)} "
            f"-H 'Content-Type: application/json' -d {shlex.quote(corps)} {FOURNISSEUR}/present"
        )
        assert res.stdout.strip() == "403", message(
            en=f"Account {nom!r} published a record outside its zone "
            f"(compta.lab.test answered {res.stdout.strip()}).",
            fr=f"Le compte {nom!r} a publié un enregistrement hors de sa zone "
            f"(compta.lab.test a répondu {res.stdout.strip()}).",
        )


def test_03_l_autorite_valide_vraiment_le_dns(edge) -> None:
    """L'autorité de test n'a pas été affaiblie pour émettre sans contrôler.

    Pebble sait valider tout défi sans le vérifier (PEBBLE_VA_ALWAYS_VALID), ou
    interroger un autre serveur DNS que celui du banc. L'un ou l'autre ferait
    passer un joker obtenu sans DNS-01 réel : la plateforme doit être celle que
    le banc a posée, à l'octet près.
    """
    _exiger_joker(edge)
    empreintes = edge.run(f"sudo sha256sum -c {EMPREINTES}")
    assert empreintes.rc == 0, message(
        en="The test platform (platform.yaml or pebble-config.json) was modified: "
        f"{empreintes.stdout.strip()}. Solve the challenge, do not weaken the authority.",
        fr="La plateforme de test (platform.yaml ou pebble-config.json) a été modifiée : "
        f"{empreintes.stdout.strip()}. Résolvez le défi, n'affaiblissez pas l'autorité.",
    )
    environnement = edge.run(
        "docker inspect pub-dns01-pebble --format '{{json .Config.Env}} {{json .Config.Cmd}}'"
    ).stdout
    assert "PEBBLE_VA_ALWAYS_VALID" not in environnement and "172.30.20.53:8053" in environnement, message(
        en=f"The running authority does not validate against the lab's DNS server: {environnement.strip()[:200]!r}.",
        fr=f"L'autorité en service ne valide pas auprès du serveur DNS du lab : {environnement.strip()[:200]!r}.",
    )


def test_04_les_enregistrements_temporaires_sont_retires(edge) -> None:
    """Chaque TXT de défi publié a été retiré ensuite.

    Un TXT oublié laisse une trace de chaque émission dans la zone, et un
    automate qui ne nettoie pas après un succès ne nettoie pas non plus après
    un échec.
    """
    _exiger_joker(edge)
    entrees = [e for e in _journal(edge) if e.get("fqdn") == DEFI and e.get("statut") == 200]
    assert entrees, message(
        en=f"No publication of {DEFI} in the provider's journal.",
        fr=f"Aucune publication de {DEFI} dans le journal du fournisseur.",
    )
    poses = [e for e in entrees if e["op"] == "/present"]
    retraits = [e for e in entrees if e["op"] == "/cleanup"]
    assert len(retraits) >= len(poses), message(
        en=f"{len(poses)} challenge record(s) published, {len(retraits)} removed: "
        "a temporary TXT stays in the zone.",
        fr=f"{len(poses)} enregistrement(s) de défi publié(s), {len(retraits)} "
        "retiré(s) : un TXT temporaire reste dans la zone.",
    )
    assert entrees[-1]["op"] == "/cleanup", message(
        en="The last operation on the challenge record is a publication, not a removal.",
        fr="La dernière opération sur l'enregistrement de défi est une publication, "
        "pas un retrait.",
    )
