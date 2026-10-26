"""Verify the cache applies the content contract: public responses are really
served from cache, language variants stay apart, no private response ever
reaches another account, and volatile content stays fresh.

CE QUE CES TESTS NE LISENT JAMAIS : X-CACHE-STATUS

La situation posee ajoute `add_header X-Cache-Status "HIT" always`, qui
annonce HIT sur toutes les reponses, y compris celles qui viennent de
traverser l'origine. C'est une declaration de Nginx, pas une mesure, et
c'est Nginx qu'on verifie.

La mesure se prend donc a l'origine, sur la boucle locale de la VM, ou
Nginx n'a aucune prise : l'application compte ses GENERATIONS DE CORPS, et
un HIT devient un fait verifiable, une reponse rendue sans que l'origine
ait rien produit. Un 304 ne compte pas, pour qu'une politique de
revalidation puisse passer la mesure au meme titre qu'une duree courte.

CHAQUE MESURE PART D'UNE ENTREE FROIDE

Les chemins portent un jeton unique par mesure, que l'origine ignore et
qui designe la meme ressource. Sans lui, un test heriterait du cache du
precedent, et conclurait sur un etat qu'il n'a pas pose.
"""

from __future__ import annotations

import time
import uuid

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
ORIGINE = "http://127.0.0.1:18099"


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _jeton() -> str:
    return uuid.uuid4().hex[:12]


def _generations(edge) -> dict[str, int]:
    """Les compteurs de l'origine, lus sur la boucle locale de la VM.

    C'est le seul endroit d'ou un HIT se mesure, et le seul ou Nginx ne
    peut rien ecrire.
    """
    sortie = edge.run(f"curl -s --max-time 5 {ORIGINE}/compteur").stdout
    couples = [p.split("=") for p in sortie.split() if "=" in p]
    assert couples, message(
        en=(
            f"The origin did not answer on 127.0.0.1:18099 (got {sortie!r}). "
            "The lab cannot be graded without it: check "
            "`systemctl status pub-nginx-cache-app`."
        ),
        fr=(
            f"L'origine n'a pas répondu sur 127.0.0.1:18099 (reçu {sortie!r}). "
            "Le lab ne peut pas être évalué sans elle : regardez "
            "`systemctl status pub-nginx-cache-app`."
        ),
    )
    return {cle: int(valeur) for cle, valeur in couples}


def _demander(poste, ip: str, chemin: str, entetes: str = "") -> tuple[str, str]:
    """Le code de statut et le corps, demandes depuis le client."""
    sortie = poste.run(
        f"curl -s --max-time 10 -w '\\n%{{http_code}}' "
        f"-H 'Host: catalogue.lab.test' {entetes} http://{ip}{chemin}"
    ).stdout
    if "\n" not in sortie:
        return "000", sortie
    corps, code = sortie.rsplit("\n", 1)
    return code.strip(), corps


def test_une_reponse_publique_est_reellement_servie_depuis_le_cache(
    poste, edge, ip_edge
) -> None:
    """L'ancrage, et la mesure qu'aucun en-tete ne peut fabriquer.

    Deux demandes de suite sur la meme ressource publique stable. La
    premiere doit faire produire un corps a l'origine, la seconde ne doit
    rien lui faire produire du tout.
    """
    chemin = f"/catalogue/accueil/{_jeton()}"

    avant = _generations(edge)
    code1, corps1 = _demander(poste, ip_edge, chemin)
    milieu = _generations(edge)
    code2, corps2 = _demander(poste, ip_edge, chemin)
    apres = _generations(edge)

    assert code1 == "200" and code2 == "200", message(
        en=(
            f"The public home page answered {code1} then {code2}, not 200 "
            "twice. Before caching anything, the route has to work."
        ),
        fr=(
            f"La page d'accueil publique a répondu {code1} puis {code2}, et "
            "non 200 deux fois. Avant de mettre en cache, la route doit "
            "fonctionner."
        ),
    )

    premier = milieu["accueil"] - avant["accueil"]
    assert premier >= 1, message(
        en=(
            "The first request on a cold entry produced nothing at the origin. "
            "The path carries a token unique to this run, so the entry cannot "
            "have been warm: something is answering instead of the origin."
        ),
        fr=(
            "La première demande sur une entrée froide n'a rien fait produire "
            "à l'origine. Le chemin porte un jeton unique à cette mesure, donc "
            "l'entrée ne pouvait pas être chaude : quelque chose répond à la "
            "place de l'origine."
        ),
    )

    second = apres["accueil"] - milieu["accueil"]
    assert second == 0, message(
        en=(
            f"The second request made the origin generate {second} more "
            "body/bodies: the public response is not being served from cache. "
            "Note that this is measured at the origin, not read from "
            "X-Cache-Status, which the posed configuration sets to HIT on "
            "every response including the misses."
        ),
        fr=(
            f"La seconde demande a fait produire {second} corps de plus à "
            "l'origine : la réponse publique n'est pas servie depuis le cache. "
            "La mesure est prise à l'origine, et non lue dans X-Cache-Status, "
            "que la situation posée affiche à HIT sur toutes les réponses, y "
            "compris les MISS."
        ),
    )

    assert corps1 == corps2, message(
        en=(
            "The two responses differ although the resource is stable: "
            f"{corps1!r} then {corps2!r}."
        ),
        fr=(
            "Les deux réponses diffèrent alors que la ressource est stable : "
            f"{corps1!r} puis {corps2!r}."
        ),
    )


def test_les_variantes_de_langue_ne_se_melangent_pas(poste, edge, ip_edge) -> None:
    """Deux representations, deux entrees.

    Et le contre-exemple dans le meme test : la variante francaise reste
    servie depuis le cache. Sans lui, « ne rien mettre en cache » passerait.
    """
    chemin = f"/catalogue/fiche/{_jeton()}"

    _, corps_fr = _demander(poste, ip_edge, chemin, "-H 'Accept-Language: fr'")
    assert "francais" in corps_fr, message(
        en=(
            f"Asked in French, the product sheet answered {corps_fr!r}. The "
            "origin varies on Accept-Language: this is the reference the rest "
            "of the test compares against."
        ),
        fr=(
            f"Demandée en français, la fiche produit a répondu {corps_fr!r}. "
            "L'origine varie selon Accept-Language : c'est la référence à "
            "laquelle le reste du test se compare."
        ),
    )

    _, corps_en = _demander(poste, ip_edge, chemin, "-H 'Accept-Language: en'")
    assert "english" in corps_en, message(
        en=(
            f"Asked in English, the product sheet answered {corps_en!r}: the "
            "French variant was served from cache for an English request. The "
            "cache key does not see the language, and the origin's "
            "`Vary: Accept-Language` is being ignored."
        ),
        fr=(
            f"Demandée en anglais, la fiche produit a répondu {corps_en!r} : "
            "la variante française a été servie depuis le cache à une demande "
            "anglaise. La clé de cache ne voit pas la langue, et le "
            "`Vary: Accept-Language` de l'origine est ignoré."
        ),
    )

    avant = _generations(edge)
    _, encore_fr = _demander(poste, ip_edge, chemin, "-H 'Accept-Language: fr'")
    apres = _generations(edge)
    assert encore_fr == corps_fr, message(
        en=f"The French variant changed between two requests: {encore_fr!r}.",
        fr=(
            "La variante française a changé entre deux demandes : "
            f"{encore_fr!r}."
        ),
    )
    assert apres["fiche"] - avant["fiche"] == 0, message(
        en=(
            "Separating the variants was done by giving up caching them: the "
            "French variant went back to the origin although it had already "
            "been served. Both representations are public and cacheable; they "
            "need two entries, not none."
        ),
        fr=(
            "Les variantes ont été séparées en renonçant à les mettre en "
            "cache : la variante française est repartie à l'origine alors "
            "qu'elle avait déjà été servie. Les deux représentations sont "
            "publiques et éligibles : il leur faut deux entrées, pas zéro."
        ),
    )


def test_aucune_reponse_privee_ne_passe_a_l_autre_compte(
    poste, edge, ip_edge
) -> None:
    """CRITIQUE. Le marqueur d'un compte ne doit jamais atteindre l'autre.

    Les deux marqueurs sont tires au hasard par la fixture, et lus ici a
    l'origine : un corps fixe ne prouverait rien, puisqu'il serait le meme
    des deux cotes.
    """
    nonce_alpha = edge.run(
        f"curl -s --max-time 5 --cookie 'session=alpha' {ORIGINE}/compte/prive"
    ).stdout.strip()
    nonce_beta = edge.run(
        f"curl -s --max-time 5 --cookie 'session=beta' {ORIGINE}/compte/prive"
    ).stdout.strip()
    marqueur_alpha = nonce_alpha.rsplit(" ", 1)[-1]
    marqueur_beta = nonce_beta.rsplit(" ", 1)[-1]
    assert marqueur_alpha and marqueur_alpha != marqueur_beta, message(
        en=(
            "The origin did not hand out two distinct markers "
            f"({nonce_alpha!r} / {nonce_beta!r}); the leak cannot be measured. "
            "Check that /opt/pub-nginx-cache/etat/nonce-*.txt are readable."
        ),
        fr=(
            "L'origine n'a pas rendu deux marqueurs distincts "
            f"({nonce_alpha!r} / {nonce_beta!r}) ; la fuite ne peut pas être "
            "mesurée. Vérifiez que /opt/pub-nginx-cache/etat/nonce-*.txt sont "
            "lisibles."
        ),
    )

    chemin = f"/compte/prive/{_jeton()}"

    code_a, corps_a = _demander(
        poste, ip_edge, "/compte/prive", "--cookie 'session=alpha'"
    )
    assert code_a == "200" and marqueur_alpha in corps_a, message(
        en=(
            f"The alpha account answered {code_a} / {corps_a!r} and does not "
            "carry its own marker. The private route has to work for its owner "
            "before the leak can mean anything."
        ),
        fr=(
            f"Le compte alpha a répondu {code_a} / {corps_a!r} et ne porte pas "
            "son propre marqueur. La route privée doit fonctionner pour son "
            "titulaire avant que la fuite veuille dire quelque chose."
        ),
    )

    code_b, corps_b = _demander(
        poste, ip_edge, "/compte/prive", "--cookie 'session=beta'"
    )
    assert marqueur_alpha not in corps_b, message(
        en=(
            "The beta account received the alpha account's marker: a private, "
            "authenticated response was cached and handed to another session. "
            "The origin says `Cache-Control: private, no-store` on it, and the "
            "posed configuration throws that away with "
            "`proxy_ignore_headers Cache-Control`."
        ),
        fr=(
            "Le compte beta a reçu le marqueur du compte alpha : une réponse "
            "privée authentifiée a été mise en cache puis rendue à une autre "
            "session. L'origine l'annonce en `Cache-Control: private, "
            "no-store`, et la situation posée jette ce contrat avec "
            "`proxy_ignore_headers Cache-Control`."
        ),
    )
    assert code_b == "200" and marqueur_beta in corps_b, message(
        en=(
            f"The beta account answered {code_b} / {corps_b!r}: it did not get "
            "the leak, but it did not get its own data either."
        ),
        fr=(
            f"Le compte beta a répondu {code_b} / {corps_b!r} : il n'a pas reçu "
            "la fuite, mais il n'a pas reçu ses propres données non plus."
        ),
    )

    code_sans, corps_sans = _demander(poste, ip_edge, chemin)
    assert code_sans == "401", message(
        en=(
            f"With no session cookie, the private route answered {code_sans} / "
            f"{corps_sans!r} instead of 401."
        ),
        fr=(
            "Sans cookie de session, la route privée a répondu "
            f"{code_sans} / {corps_sans!r} au lieu de 401."
        ),
    )
    for marqueur, compte in ((marqueur_alpha, "alpha"), (marqueur_beta, "beta")):
        assert marqueur not in corps_sans, message(
            en=(
                f"An anonymous request received the {compte} account's marker: "
                "a cached private response is being served to whoever asks."
            ),
            fr=(
                f"Une demande anonyme a reçu le marqueur du compte {compte} : "
                "une réponse privée en cache est servie à qui la demande."
            ),
        )

    # Le contre-exemple. Sans lui, « proxy_cache off » partout passerait ce
    # test en ayant retire le cache au lieu de le corriger.
    public = f"/catalogue/accueil/{_jeton()}"
    _demander(poste, ip_edge, public)
    avant = _generations(edge)
    _demander(poste, ip_edge, public)
    apres = _generations(edge)
    assert apres["accueil"] - avant["accueil"] == 0, message(
        en=(
            "Private responses no longer leak, but the public home page is not "
            "cached either: the cache was removed rather than corrected. The "
            "contract declares that page eligible."
        ),
        fr=(
            "Les réponses privées ne fuient plus, mais la page d'accueil "
            "publique n'est plus mise en cache non plus : le cache a été retiré "
            "au lieu d'être corrigé. Le contrat déclare cette page éligible."
        ),
    )


def test_la_fraicheur_du_contenu_volatil_suit_le_contrat(
    poste, edge, ip_edge
) -> None:
    """Le stock bouge, et ne doit jamais etre servi vieux de plus de cinq
    secondes. Il reste neanmoins eligible : deux demandes qui se suivent ne
    doivent pas faire produire deux corps.

    Les deux cotes comptent. Une duree de zero tiendrait la fraicheur en
    renoncant au cache ; une duree de dix minutes tiendrait le cache en
    servant un etat mort.
    """
    chemin = f"/catalogue/stock/{_jeton()}"

    _demander(poste, ip_edge, chemin)
    avant = _generations(edge)
    _demander(poste, ip_edge, chemin)
    apres = _generations(edge)
    assert apres["stock"] - avant["stock"] == 0, message(
        en=(
            "Two back-to-back requests made the origin generate two bodies: "
            "the volatile resource is not cached at all. Freshness was bought "
            "by giving up caching, and the contract asks for both. A short TTL "
            "or `proxy_cache_revalidate on` both pass this measure, because a "
            "304 is not counted as a generation."
        ),
        fr=(
            "Deux demandes qui se suivent ont fait produire deux corps à "
            "l'origine : la ressource volatile n'est pas mise en cache du "
            "tout. La fraîcheur a été achetée en renonçant au cache, et le "
            "contrat demande les deux. Une durée courte comme "
            "`proxy_cache_revalidate on` passent cette mesure, puisqu'un 304 "
            "n'est pas compté comme une génération."
        ),
    )

    nouveau = edge.run(
        f"curl -s --max-time 5 -X POST {ORIGINE}/muter"
    ).stdout.strip()
    valeur = nouveau.split("=", 1)[-1]
    assert valeur and valeur != "stock-initial", message(
        en=(
            f"The origin did not change its stock value (answered {nouveau!r}); "
            "freshness cannot be measured."
        ),
        fr=(
            f"L'origine n'a pas changé son état de stock (réponse {nouveau!r}) ; "
            "la fraîcheur ne peut pas être mesurée."
        ),
    )

    time.sleep(7)
    _, corps = _demander(poste, ip_edge, chemin)
    assert valeur in corps, message(
        en=(
            f"Seven seconds after the origin changed, the answer is still "
            f"{corps!r} and does not carry the new value {valeur}. The contract "
            "says never to serve a stock state older than five seconds: the "
            "origin announces `Cache-Control: public, max-age=5` on that "
            "response, and the posed configuration throws it away to keep "
            "everything for ten minutes."
        ),
        fr=(
            "Sept secondes après le changement à l'origine, la réponse est "
            f"encore {corps!r} et ne porte pas la nouvelle valeur {valeur}. Le "
            "contrat interdit de servir un état de stock vieux de plus de cinq "
            "secondes : l'origine annonce `Cache-Control: public, max-age=5` "
            "sur cette réponse, et la situation posée la jette pour tout garder "
            "dix minutes."
        ),
    )
