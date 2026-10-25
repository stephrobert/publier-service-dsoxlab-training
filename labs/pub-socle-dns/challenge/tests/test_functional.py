"""Vérifie la bascule DNS telle qu'un utilisateur la vit, depuis le client.

Le test appelle lui-même le script de l'apprenant dans les deux sens, puis
récupère le site à travers le résolveur à cache, sans jamais forcer
l'adresse : seul le DNS décide de la version qui répond.
"""

from __future__ import annotations

import json
import re
import time

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
FICHE = "/home/student/dns.yaml"
SCRIPT = "/home/student/basculer.sh"
ETAT = "/var/lib/pub-dns/etat.json"
ATTENTE_MAX = 20


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def client():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


def _version_vue(client, famille: str) -> str:
    return client.run(
        f"curl -{famille} --silent --max-time 3 http://shop.pub.test/"
    ).stdout.strip()


def _attendre(client, etat, version: str) -> tuple[str, str]:
    attendu = f"{version}-{etat['token']}"
    vu4 = vu6 = ""
    for _ in range(ATTENTE_MAX):
        vu4, vu6 = _version_vue(client, "4"), _version_vue(client, "6")
        if vu4 == attendu and vu6 == attendu:
            break
        time.sleep(1)
    return vu4, vu6


def _basculer(edge, client, etat, version: str) -> None:
    res = edge.run(f"timeout 60 bash {SCRIPT} {version}")
    assert res.rc == 0, message(
        en=f"'basculer.sh {version}' failed (rc={res.rc}): {res.stderr.strip()}",
        fr=f"'basculer.sh {version}' a échoué (rc={res.rc}) : {res.stderr.strip()}",
    )
    attendu = f"{version}-{etat['token']}"
    vu4, vu6 = _attendre(client, etat, version)
    assert vu4 == attendu, message(
        en=f"Over IPv4 the client sees '{vu4}' instead of '{attendu}' after {ATTENTE_MAX}s.",
        fr=f"En IPv4 le client voit '{vu4}' au lieu de '{attendu}' après {ATTENTE_MAX} s.",
    )
    assert vu6 == attendu, message(
        en=f"Over IPv6 the client sees '{vu6}' instead of '{attendu}' after {ATTENTE_MAX}s (AAAA forgotten?).",
        fr=f"En IPv6 le client voit '{vu6}' au lieu de '{attendu}' après {ATTENTE_MAX} s (AAAA oublié ?).",
    )


def test_fiche_conforme_au_systeme(edge, etat) -> None:
    fichier = edge.file(FICHE)
    assert fichier.exists, message(en=f"{FICHE} does not exist.", fr=f"{FICHE} n'existe pas.")
    try:
        fiche = yaml.safe_load(fichier.content_string)
    except yaml.YAMLError as erreur:
        pytest.fail(message(en=f"{FICHE} is not valid YAML: {erreur}",
                            fr=f"{FICHE} n'est pas un YAML valide : {erreur}"))
    assert isinstance(fiche, dict), message(
        en=f"{FICHE} must contain a YAML mapping.", fr=f"{FICHE} doit contenir un dictionnaire YAML."
    )
    autoritaire = str(fiche.get("serveur_autoritaire", "")).strip()
    reponse = edge.run(
        f"dig +norecurse +noall +comments @{autoritaire} shop.pub.test A 2>/dev/null"
    ).stdout
    drapeaux = re.findall(r"flags: ([a-z ]+);", reponse)
    assert autoritaire and drapeaux and "aa" in drapeaux[0].split(), message(
        en="'serveur_autoritaire' is not the server that answers authoritatively (aa flag) for pub.test.",
        fr="'serveur_autoritaire' n'est pas le serveur qui répond avec autorité (drapeau aa) pour pub.test.",
    )
    assert fiche.get("ttl_initial") == etat["ttl"], message(
        en=f"'ttl_initial' is wrong: the zone was published with a TTL of {etat['ttl']} seconds.",
        fr=f"'ttl_initial' est faux : la zone était publiée avec un TTL de {etat['ttl']} secondes.",
    )
    assert sorted(map(str, fiche.get("types_a_basculer") or [])) == ["A", "AAAA"], message(
        en="'types_a_basculer' must list the two record types the site is reached through: A and AAAA.",
        fr="'types_a_basculer' doit lister les deux types d'enregistrement par lesquels le site est joint : A et AAAA.",
    )


def test_bascule_aller_retour_vue_du_client(edge, client, etat) -> None:
    assert edge.file(SCRIPT).exists, message(
        en=f"{SCRIPT} does not exist.", fr=f"{SCRIPT} n'existe pas."
    )
    _basculer(edge, client, etat, "v2")
    _basculer(edge, client, etat, "v1")
    _basculer(edge, client, etat, "v2")


def test_zone_reste_valide_et_ttl_court(edge, etat) -> None:
    sortie = edge.run("dig +noall +answer @127.0.0.2 shop.pub.test A").stdout.split()
    assert sortie, message(
        en="The authoritative server no longer answers for shop.pub.test.",
        fr="Le serveur faisant autorité ne répond plus pour shop.pub.test.",
    )
    assert sortie[-1] == etat["v2_4"], message(
        en="The zone must finish pointing to v2 over IPv4.",
        fr="La zone doit finir en v2 pour l'IPv4.",
    )
    assert int(sortie[1]) <= 60, message(
        en=f"The TTL of shop is still {sortie[1]}s: a switch back would not reach users quickly.",
        fr=f"Le TTL de shop est encore de {sortie[1]} s : un retour arrière n'atteindrait pas vite les utilisateurs.",
    )
