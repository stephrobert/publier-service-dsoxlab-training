"""Vérifie que les quatre points d'accès TLS prouvent, ou non, leur identité.

Les tests sondent eux-mêmes les quatre points d'accès avec `openssl s_client`,
la racine de confiance remise à l'apprenant et une vérification complète du
nom et de la chaîne : jamais `-k`/`--insecure`. Seul le code de vérification
réellement observé compte, jamais le texte de la fiche de l'apprenant.
"""

from __future__ import annotations

import json
import re

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
FICHE = "/home/student/verdict.yaml"
ETAT = "/etc/pub-tls/etat.json"
CA = "/home/student/ca.pem"
SERVICES = ("positif", "nom", "chaine", "date")
CAUSES = {"aucune", "nom", "chaine", "date"}

# Un code de vérification OpenSSL appartient à l'une de ces trois familles de
# cause, ou à aucune (0 = ok). Peu importe la variante exacte du message :
# c'est la famille qui compte, pas le libellé.
CODES_NOM = {62}
CODES_DATE = {9, 10}


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def etat(edge):
    brut = edge.run(f"sudo cat {ETAT}").stdout
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        pytest.fail(message(en=f"{ETAT} is not valid JSON.", fr=f"{ETAT} n'est pas un JSON valide."))


@pytest.fixture(scope="module")
def fiche(edge):
    fichier = edge.file(FICHE)
    assert fichier.exists, message(en=f"{FICHE} does not exist.", fr=f"{FICHE} n'existe pas.")
    try:
        contenu = yaml.safe_load(fichier.content_string)
    except yaml.YAMLError as erreur:
        pytest.fail(message(
            en=f"{FICHE} is not valid YAML: {erreur}",
            fr=f"{FICHE} n'est pas un YAML valide : {erreur}",
        ))
    verdict = (contenu or {}).get("verdict")
    assert isinstance(verdict, dict), message(
        en="'verdict' must be a mapping.", fr="'verdict' doit être un dictionnaire."
    )
    for nom in SERVICES:
        ligne = verdict.get(nom)
        assert isinstance(ligne, dict), message(
            en=f"'verdict.{nom}' is missing or is not a mapping.",
            fr=f"'verdict.{nom}' est absent ou n'est pas un dictionnaire.",
        )
        assert isinstance(ligne.get("accepte"), bool), message(
            en=f"'verdict.{nom}.accepte' must be a boolean.",
            fr=f"'verdict.{nom}.accepte' doit être un booléen.",
        )
        assert ligne.get("cause") in CAUSES, message(
            en=f"'verdict.{nom}.cause' must be one of {sorted(CAUSES)}.",
            fr=f"'verdict.{nom}.cause' doit valoir l'une de {sorted(CAUSES)}.",
        )
        assert ligne["accepte"] == (ligne["cause"] == "aucune"), message(
            en=f"'verdict.{nom}': 'cause' must be 'aucune' exactly when 'accepte' is true.",
            fr=f"'verdict.{nom}' : 'cause' doit valoir 'aucune' exactement quand 'accepte' vaut true.",
        )
    return verdict


def _code_verification(edge, nom: str, port: int) -> int | None:
    """Code de vérification OpenSSL réellement observé en se connectant."""
    sonde = (
        f"printf '' | timeout 5 openssl s_client -connect 127.0.0.1:{port} "
        f"-servername {nom} -verify_hostname {nom} -CAfile {CA} 2>&1 || true"
    )
    sortie = edge.run(sonde).stdout
    trouve = re.search(r"Verify return code:\s*(\d+)", sortie)
    assert trouve, message(
        en=f"No TLS verification code observed on port {port}: the endpoint may not answer.",
        fr=f"Aucun code de vérification TLS observé sur le port {port} : le point d'accès ne répond peut-être pas.",
    )
    return int(trouve.group(1))


def _cause_reelle(code: int) -> tuple[bool, str]:
    if code == 0:
        return True, "aucune"
    if code in CODES_NOM:
        return False, "nom"
    if code in CODES_DATE:
        return False, "date"
    return False, "chaine"


@pytest.fixture(scope="module")
def observation(edge, etat) -> dict[str, tuple[bool, str]]:
    return {
        nom: _cause_reelle(_code_verification(edge, etat["nom"], etat["ports"][nom]))
        for nom in SERVICES
    }


def test_positif_accepte_avec_la_chaine_complete(edge, etat, fiche, observation) -> None:
    accepte, cause = observation["positif"]
    assert (accepte, cause) == (True, "aucune"), message(
        en="The 'positif' endpoint must verify (code 0) against the given root: check its chain.",
        fr="Le point d'accès 'positif' doit se vérifier (code 0) face à la racine fournie : vérifiez sa chaîne.",
    )
    assert fiche["positif"] == {"accepte": True, "cause": "aucune"}, message(
        en="'verdict.positif' must say the endpoint is accepted, with no cause.",
        fr="'verdict.positif' doit dire le point d'accès accepté, sans cause.",
    )
    reponse = edge.run(
        "printf 'GET / HTTP/1.0\\r\\n\\r\\n' | "
        f"timeout 5 openssl s_client -connect 127.0.0.1:{etat['ports']['positif']} "
        f"-servername {etat['nom']} -CAfile {CA} -quiet 2>/dev/null"
    ).stdout
    assert "pub-tls-ok positif" in reponse, message(
        en="The verified connection to 'positif' did not reach the application behind it.",
        fr="La connexion vérifiée vers 'positif' n'a pas atteint l'application derrière.",
    )


def test_nom_refuse_a_cause_du_nom(fiche, observation) -> None:
    """Point critique : un SAN qui ne couvre pas le nom demandé est refusé."""
    accepte, cause = observation["nom"]
    assert (accepte, cause) == (False, "nom"), message(
        en="The 'nom' endpoint must fail verification because of a hostname mismatch.",
        fr="Le point d'accès 'nom' doit échouer la vérification à cause d'un nom qui ne correspond pas.",
    )
    assert fiche["nom"] == {"accepte": False, "cause": "nom"}, message(
        en="'verdict.nom' must say the endpoint is refused, cause 'nom'.",
        fr="'verdict.nom' doit dire le point d'accès refusé, cause 'nom'.",
    )


def test_chaine_refusee_a_cause_d_une_autorite_etrangere(fiche, observation) -> None:
    """Point critique : une chaîne invalide ou une autorité étrangère est refusée."""
    accepte, cause = observation["chaine"]
    assert (accepte, cause) == (False, "chaine"), message(
        en="The 'chaine' endpoint must fail verification because its issuer is not the given root.",
        fr="Le point d'accès 'chaine' doit échouer la vérification car son autorité n'est pas la racine fournie.",
    )
    assert fiche["chaine"] == {"accepte": False, "cause": "chaine"}, message(
        en="'verdict.chaine' must say the endpoint is refused, cause 'chaine'.",
        fr="'verdict.chaine' doit dire le point d'accès refusé, cause 'chaine'.",
    )


def test_date_refusee_hors_periode_de_validite(fiche, observation) -> None:
    """Point critique : un certificat hors période est refusé, sans toucher
    à l'horloge réelle de l'hôte."""
    accepte, cause = observation["date"]
    assert (accepte, cause) == (False, "date"), message(
        en="The 'date' endpoint must fail verification because of its validity dates.",
        fr="Le point d'accès 'date' doit échouer la vérification à cause de ses dates de validité.",
    )
    assert fiche["date"] == {"accepte": False, "cause": "date"}, message(
        en="'verdict.date' must say the endpoint is refused, cause 'date'.",
        fr="'verdict.date' doit dire le point d'accès refusé, cause 'date'.",
    )


def test_verdict_conforme_a_l_observation_pour_les_quatre_points(fiche, observation) -> None:
    for nom in SERVICES:
        accepte, cause = observation[nom]
        assert fiche[nom] == {"accepte": accepte, "cause": cause}, message(
            en=f"'verdict.{nom}' does not match what is really observed (accepte={accepte}, cause={cause}).",
            fr=f"'verdict.{nom}' ne correspond pas à ce qui est réellement observé (accepte={accepte}, cause={cause}).",
        )
