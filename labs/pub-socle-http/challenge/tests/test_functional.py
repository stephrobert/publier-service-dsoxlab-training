"""Vérifie la recette HTTP contre ce que le backend a réellement reçu et écrit.

Les vérités viennent du journal de l'API, jamais du texte du corrigé : les
tests rejouent eux-mêmes les redirections et les envois, avec des données
tirées au hasard.
"""

from __future__ import annotations

import json
import re
import secrets

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
RECETTE = "/home/student/recette-http.yaml"
CLIENT = "/home/student/envoyer-commande.sh"
README = "/home/student/README-api"
ETAT = "/var/lib/pub-api"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def url(edge):
    brut = edge.run("systemctl show pub-api --property=Environment --value").stdout
    port = re.search(r"API_PORT=(\d+)", brut)
    assert port, message(en="The API is not configured.", fr="L'API n'est pas configurée.")
    return f"http://127.0.0.1:{port.group(1)}"


def _journal(edge, nom):
    contenu = edge.run(f"sudo cat {ETAT}/{nom} 2>/dev/null").stdout
    return [json.loads(ligne) for ligne in contenu.splitlines() if ligne.strip()]


def _lire_yaml(edge):
    fichier = edge.file(RECETTE)
    assert fichier.exists, message(
        en=f"{RECETTE} does not exist.", fr=f"{RECETTE} n'existe pas."
    )
    try:
        contenu = yaml.safe_load(fichier.content_string)
    except yaml.YAMLError as erreur:
        pytest.fail(message(en=f"{RECETTE} is not valid YAML: {erreur}",
                            fr=f"{RECETTE} n'est pas un YAML valide : {erreur}"))
    assert isinstance(contenu, dict), message(
        en=f"{RECETTE} must contain a YAML mapping.",
        fr=f"{RECETTE} doit contenir un dictionnaire YAML.",
    )
    return contenu


def test_requete_de_recette_recue_par_le_backend(edge) -> None:
    jeton = re.search(r"Jeton de recette : (\w+)", edge.file(README).content_string).group(1)
    recues = [
        r for r in _journal(edge, "recu.jsonl")
        if r["methode"] == "POST" and r["chemin"] == "/commandes"
        and r["entetes"].get("x-recette") == jeton
        and "jeton" in r["corps"] and json.loads(r["corps"]).get("jeton") == jeton
    ]
    assert recues, message(
        en="The backend never received a POST /commandes carrying the recette token in both the X-Recette header and the JSON body.",
        fr="Le backend n'a jamais reçu de POST /commandes portant le jeton de recette dans l'en-tête X-Recette et dans le corps JSON.",
    )


def test_redirections_documentees_selon_le_backend(edge, url) -> None:
    recette = _lire_yaml(edge).get("redirections") or {}
    for code in (301, 302, 303, 307, 308):
        ref = f"redir-{secrets.token_hex(4)}"
        avant = len(_journal(edge, "recu.jsonl"))
        edge.run(
            f"curl --silent --location --output /dev/null --max-time 5 "
            f"-H 'Content-Type: application/json' -d '{{\"ref\":\"{ref}\"}}' "
            f"{url}/redir/{code}/commandes"
        )
        nouvelles = _journal(edge, "recu.jsonl")[avant:]
        finale = [r for r in nouvelles if r["chemin"] == "/commandes"]
        assert finale, message(
            en=f"The redirect {code} was not followed to /commandes.",
            fr=f"La redirection {code} n'a pas été suivie jusqu'à /commandes.",
        )
        reelle = finale[-1]["methode"]
        assert str(recette.get(code, "")).upper() == reelle, message(
            en=f"'redirections.{code}' is wrong: the backend received {reelle}.",
            fr=f"'redirections.{code}' est faux : le backend a reçu {reelle}.",
        )


def test_statuts_documentes_selon_le_serveur(edge, url) -> None:
    statuts = _lire_yaml(edge).get("statuts") or {}
    for route in ("/refus", "/erreur", "/inconnue"):
        reel = edge.run(
            f"curl --silent --output /dev/null --max-time 5 "
            f"--write-out '%{{http_code}}' {url}{route}"
        ).stdout.strip()
        assert str(statuts.get(route, "")) == reel, message(
            en=f"'statuts.{route}' is wrong: the server answers {reel}.",
            fr=f"'statuts.{route}' est faux : le serveur répond {reel}.",
        )


@pytest.mark.parametrize("prefixe", ["normale", "perdue"])
def test_commande_jamais_dupliquee_meme_si_la_reponse_est_perdue(edge, url, prefixe) -> None:
    ref = f"{prefixe}-{secrets.token_hex(4)}"
    assert edge.file(CLIENT).exists, message(
        en=f"{CLIENT} does not exist.", fr=f"{CLIENT} n'existe pas."
    )
    res = edge.run(f"timeout 60 bash {CLIENT} {url} {ref}")
    ecritures = [e for e in _journal(edge, "ecritures.jsonl") if e["ref"] == ref]
    existe = edge.run(
        f"curl --silent --output /dev/null --write-out '%{{http_code}}' {url}/commandes/{ref}"
    ).stdout.strip()
    assert res.rc == 0 and existe == "200", message(
        en=f"The client must exit 0 once the order {ref} exists (rc={res.rc}, GET status {existe}).",
        fr=f"Le client doit sortir en 0 une fois la commande {ref} créée (rc={res.rc}, GET {existe}).",
    )
    assert len(ecritures) == 1, message(
        en=f"The order {ref} was written {len(ecritures)} times instead of once.",
        fr=f"La commande {ref} a été écrite {len(ecritures)} fois au lieu d'une.",
    )
