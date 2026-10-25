"""Vérifie, depuis un vrai navigateur et pas seulement un en-tête curl, que
le parcours de connexion aboutit sans boucle, que la session légitime
fonctionne dans le navigateur, que l'origine autorisée fonctionne alors
qu'une autre n'obtient pas la lecture, et qu'un en-tête d'identité forgé
depuis le client n'accorde jamais l'accès au compte.

Chaque vérification lance le navigateur automatisable fourni
(`verifier_navigateur.py`, Playwright + Chromium, déjà installé sur
edge.lab par `prepare.sh`) depuis edge.lab lui-même, puisque c'est là que
tout tourne en boucle locale (127.0.0.1).
"""

from __future__ import annotations

import json

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
ETAT = "/var/lib/pub-app/etat.json"
SCRIPT = "/opt/pub-app/verifier_navigateur.py"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


def _verifier(edge, *args: str) -> dict:
    cmd = "sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright python3 " + SCRIPT + " " + " ".join(
        str(a) for a in args
    )
    res = edge.run(cmd)
    assert res.rc == 0, message(
        en=f"The provided automated browser failed (rc={res.rc}): {res.stderr}",
        fr=f"Le navigateur automatisable fourni a échoué (rc={res.rc}) : {res.stderr}",
    )
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        pytest.fail(
            message(
                en=f"The automated browser did not print valid JSON: {res.stdout!r}",
                fr=f"Le navigateur automatisable n'a pas imprimé de JSON valide : {res.stdout!r}",
            )
        )


def test_parcours_sans_boucle(edge, etat):
    """Le parcours de connexion se termine sur l'URL HTTPS attendue, sans
    boucle de redirection, et la page de compte affiche la session
    réellement utilisée dans le navigateur."""
    sortie = _verifier(edge, "parcours", etat["entree_port"])
    assert sortie["erreur"] is None, message(
        en=f"Login navigation failed, likely a redirect loop: {sortie['erreur']}",
        fr=f"La navigation de connexion a échoué, probable boucle de "
        f"redirection : {sortie['erreur']}",
    )
    assert sortie["schema_final"] == "https", message(
        en=f"The journey did not end on an HTTPS URL: {sortie['url_finale']}",
        fr=f"Le parcours ne se termine pas sur une URL HTTPS : {sortie['url_finale']}",
    )
    assert sortie["connexion_ok"], message(
        en=f"The journey did not end on the account page: {sortie['url_finale']}",
        fr=f"Le parcours ne se termine pas sur la page de compte : {sortie['url_finale']}",
    )
    assert sortie["compte_affiche"], message(
        en="The account page does not show the session as connected: the "
        "cookie scope is probably still wrong.",
        fr="La page de compte n'affiche pas la session comme connectée : "
        "la portée du cookie est probablement encore incorrecte.",
    )


def test_cors_origine_autorisee_et_refusee(edge, etat):
    """L'origine partenaire obtient l'autorisation de lecture ; l'origine
    intruse ne l'obtient pas, qu'il s'agisse du pré-vol ou de la requête
    réelle, observé depuis un vrai navigateur."""
    sortie = _verifier(edge, "cors", etat["partenaire_port"], etat["intrus_port"])
    partenaire = sortie["partenaire"]
    intrus = sortie["intrus"]
    assert partenaire.get("ok") and partenaire.get("statut") == 200, message(
        en=f"The partner origin, which is supposed to be allowed, could not "
        f"read the response: {partenaire}",
        fr=f"L'origine partenaire, censée être autorisée, n'a pas pu lire "
        f"la réponse : {partenaire}",
    )
    assert not intrus.get("ok"), message(
        en=f"The intruder origin could read the response: the CORS policy "
        f"is still excessive: {intrus}",
        fr=f"L'origine intruse a pu lire la réponse : la politique CORS "
        f"est encore excessive : {intrus}",
    )


def test_identite_forgee_sans_privilege(edge, etat):
    """Point critique : un en-tête d'identité forgé côté client, sans
    session légitime, ne doit jamais donner accès au compte protégé."""
    sortie = _verifier(edge, "identite", etat["entree_port"])
    assert not sortie["identite_reconnue"], message(
        en=f"A forged X-Pub-User header granted access to the account "
        f"without any legitimate session: {sortie}",
        fr=f"Un en-tête X-Pub-User forgé a donné accès au compte sans "
        f"aucune session légitime : {sortie}",
    )
