"""Verify location selection, the default server, redirects, and that the
learner can predict the selection rule from the live configuration.

POURQUOI LE QUATRIEME TEST NE CHERCHE AUCUN MOT

La fiche demande que la regle de selection soit « expliquee a partir de la
configuration active ». Une machine ne sait pas juger une explication : la
noter a la longueur et au vocabulaire laisserait passer un texte incoherent,
comme cela s'est produit ailleurs dans ce catalogue.

On demande donc une PREDICTION, pas une prose. L'apprenant ecrit ou chaque
URL doit atterrir, et la validation compare sa prediction a ce que le
serveur fait reellement. Predire juste sur une configuration fausse ne passe
pas ; configurer juste sans savoir le predire non plus. C'est la meme
exigence, rendue mesurable.
"""

from __future__ import annotations

import pytest
import yaml

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
PREDICTIONS = "/home/student/selection.yaml"

# La matrice que le lab exige. Elle est ecrite ici ET dans matrice.txt :
# l'apprenant doit pouvoir la lire sans lire le test.
MATRICE = {
    "/api": "api-exact",
    "/api/v1/clients": "api-versionne",
    "/apidoc": "app-racine",
    "/static/app.js": "statique",
    "/accueil": "app-racine",
}


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _gestionnaire(poste, ip: str, chemin: str, hote: str = "app.lab.test") -> str:
    """Le gestionnaire qui a REELLEMENT traite la requete.

    Il est lu dans le corps rendu par le backend, que chaque location
    renseigne. Lire la configuration dirait ce qui est ecrit ; ceci dit ce
    qui est choisi, et les deux different des qu'une regle en recouvre une
    autre.
    """
    sortie = poste.run(
        f"curl -s --max-time 10 -H 'Host: {hote}' http://{ip}{chemin}"
    ).stdout
    for morceau in sortie.split():
        if morceau.startswith("gestionnaire="):
            return morceau.split("=", 1)[1]
    return ""


def test_chaque_url_atteint_le_gestionnaire_prevu(poste, ip_edge) -> None:
    """La matrice complete, mesuree par de vraies requetes."""
    ecarts = []
    for chemin, attendu in MATRICE.items():
        obtenu = _gestionnaire(poste, ip_edge, chemin)
        if obtenu != attendu:
            ecarts.append(f"{chemin} -> {obtenu or 'aucune reponse'} (attendu {attendu})")
    assert not ecarts, message(
        en=(
            "These URLs do not reach their intended handler: "
            + " ; ".join(ecarts)
            + ". Remember Nginx picks a regex before a plain prefix, unless "
            "that prefix carries `^~`, and that an exact `=` match wins over "
            "everything."
        ),
        fr=(
            "Ces URL n'atteignent pas le gestionnaire prévu : "
            + " ; ".join(ecarts)
            + ". Rappel : Nginx préfère une regex à un préfixe simple, sauf si "
            "ce préfixe porte `^~`, et une correspondance exacte `=` l'emporte "
            "sur tout."
        ),
    )


def test_un_nom_inconnu_ne_sert_ni_l_application_ni_l_administration(
    poste, ip_edge
) -> None:
    """CRITIQUE. Sans server par defaut, le PREMIER server recoit tout.

    Et ici le premier est celui de l'administration : un nom inconnu, une
    sonde de scanner, une entree DNS oubliee, et la page d'administration
    repond.
    """
    sortie = poste.run(
        f"curl -s --max-time 10 -w '\\n@@%{{http_code}}' "
        f"-H 'Host: inconnu.exemple.test' http://{ip_edge}/"
    ).stdout
    corps, _, statut = sortie.rpartition("@@")

    assert "admin-racine" not in corps, message(
        en=(
            "An unknown host name is served the ADMINISTRATION block. Without "
            "a server marked `default_server`, Nginx hands every unmatched "
            "name to the first server in the file."
        ),
        fr=(
            "Un nom d'hôte inconnu reçoit le bloc d'ADMINISTRATION. Sans un "
            "server marqué `default_server`, Nginx confie tout nom non reconnu "
            "au premier server du fichier."
        ),
    )
    assert "app-racine" not in corps, message(
        en="An unknown host name is served the application.",
        fr="Un nom d'hôte inconnu reçoit l'application.",
    )
    # « 000 » EST UNE REPONSE VALABLE, et meme la plus stricte.
    #
    # Le `return 444` de nginx ferme la connexion SANS envoyer d'en-tete de
    # reponse : le client ne recoit donc aucun code, et curl rapporte 000.
    # Mesure du 2026-10-26 : le corrige posait ce 444, qui est la bonne
    # pratique pour un server par defaut puisqu'il ne revele rien, et le
    # test le refusait en exigeant un code qui ne peut pas arriver.
    #
    # Ce qu'on verifie reste entier : un nom inconnu ne doit servir NI
    # l'application NI l'administration, et ne doit pas recevoir 200.
    refus = statut.strip().startswith(("40", "44", "50")) or statut.strip() in ("000", "")
    assert refus, message(
        en=(
            f"An unknown host name answered HTTP {statut.strip()!r}. It must be "
            "refused, by a default server that serves nothing: either an error "
            "code, or a closed connection (`return 444`, which curl reports as "
            "000)."
        ),
        fr=(
            f"Un nom d'hôte inconnu a répondu HTTP {statut.strip()!r}. Il doit "
            "être refusé par un server par défaut qui ne sert rien : soit un "
            "code d'erreur, soit une connexion fermée (`return 444`, que curl "
            "rapporte en 000)."
        ),
    )


def test_la_redirection_conserve_l_autorite_et_ne_boucle_pas(poste, ip_edge) -> None:
    """Une redirection qui vise le prefixe dont elle part boucle a l'infini.

    `curl` suit jusqu'a sa limite puis rend une erreur : on mesure donc le
    nombre de sauts, et la destination finale.
    """
    res = poste.run(
        f"curl -s -o /dev/null --max-time 10 -L --max-redirs 5 "
        f"-w '%{{num_redirects}} %{{http_code}} %{{url_effective}}' "
        f"-H 'Host: app.lab.test' http://{ip_edge}/ancien"
    )
    champs = res.stdout.split()
    sauts = int(champs[0]) if champs and champs[0].isdigit() else 99
    final = champs[2] if len(champs) > 2 else ""

    assert sauts <= 2, message(
        en=(
            f"/ancien went through {sauts} redirects: it loops. A redirect "
            "must not target the prefix it is declared on."
        ),
        fr=(
            f"/ancien a traversé {sauts} redirections : elle boucle. Une "
            "redirection ne doit pas viser le préfixe sur lequel elle est "
            "déclarée."
        ),
    )
    assert "/nouveau" in final, message(
        en=f"/ancien should end up on /nouveau, it ended on {final!r}.",
        fr=f"/ancien doit aboutir sur /nouveau, elle a abouti sur {final!r}.",
    )
    assert "app.lab.test" in final, message(
        en=(
            f"The redirect lost the authority on the way: {final!r}. Keep the "
            "requested host rather than hard-coding a name or an address."
        ),
        fr=(
            f"La redirection a perdu l'autorité en route : {final!r}. Conservez "
            "l'hôte demandé plutôt que d'écrire en dur un nom ou une adresse."
        ),
    )


def test_la_regle_de_selection_est_predite_juste(edge, poste, ip_edge) -> None:
    """La prediction de l'apprenant est comparee a ce que le serveur fait.

    Les deux moities sont exigees, et c'est le propos : une prediction juste
    sur une configuration fausse ne prouve rien d'utile, et une
    configuration juste qu'on ne sait pas predire non plus.
    """
    brut = edge.run(f"cat {PREDICTIONS}")
    assert brut.rc == 0 and brut.stdout.strip(), message(
        en=(
            f"{PREDICTIONS} is missing. Write there, for each URL of the "
            "matrix, the handler you expect it to reach."
        ),
        fr=(
            f"{PREDICTIONS} est absent. Écrivez-y, pour chaque URL de la "
            "matrice, le gestionnaire que vous attendez."
        ),
    )
    try:
        charge = yaml.safe_load(brut.stdout) or {}
    except yaml.YAMLError as erreur:
        pytest.fail(str(erreur))
    predictions = charge.get("predictions") or {}
    assert isinstance(predictions, dict), message(
        en=f"{PREDICTIONS} must carry a `predictions` mapping.",
        fr=f"{PREDICTIONS} doit porter un dictionnaire `predictions`.",
    )

    manquantes = sorted(set(MATRICE) - set(predictions))
    assert not manquantes, message(
        en=f"These URLs are not predicted: {manquantes}.",
        fr=f"Ces URL ne sont pas prédites : {manquantes}.",
    )

    faux = []
    for chemin in MATRICE:
        reel = _gestionnaire(poste, ip_edge, chemin)
        if str(predictions[chemin]) != reel:
            faux.append(f"{chemin} : prédit {predictions[chemin]!r}, obtenu {reel!r}")
    assert not faux, message(
        en=(
            "The prediction does not match what the server actually does: "
            + " ; ".join(faux)
            + ". Reading the configuration tells you what is written; a request "
            "tells you what is chosen, and the two differ as soon as one rule "
            "overlaps another."
        ),
        fr=(
            "La prédiction ne correspond pas à ce que le serveur fait : "
            + " ; ".join(faux)
            + ". Lire la configuration dit ce qui est écrit ; une requête dit ce "
            "qui est choisi, et les deux diffèrent dès qu'une règle en recouvre "
            "une autre."
        ),
    )
