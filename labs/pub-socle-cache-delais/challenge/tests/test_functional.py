"""Verify cache reuse and its variation, private isolation, non-duplication of
a non-idempotent action, and bounded timeouts.

CE QUE LE SETUP POSE, ET POURQUOI AUCUN TEST N'EST VERT SANS TRAVAIL

Une politique de cache et de délais RAPIDE ET DANGEREUSE : elle cache `/prive`
sans distinguer les utilisateurs, elle ne varie sur rien, elle rejoue les
POST, et elle n'a aucune borne de lecture. Les quatre contrôles échouent
donc d'entrée, chacun pour sa propre raison.

LE CONTROLE QUI NE SE DEVINE PAS

Le troisième. L'application incrémente son compteur PUIS coupe la connexion
sans répondre. Le client ne peut donc pas savoir si l'action a eu lieu : il
voit la même chose dans les deux cas. Seul le compteur métier le sait, et
c'est lui que la validation lit. C'est aussi pourquoi la décision de rejouer
se prend sur la MÉTHODE et jamais sur ce qu'on observe.
"""

from __future__ import annotations

import json
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
WORK = "/opt/pub-socle-cache-delais"
COMPTEUR = f"{WORK}/commandes.json"

ALICE = "jeton-alice-3b21"
BOB = "jeton-bob-9d47"


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _get(poste, ip: str, chemin: str, jeton: str = "", langue: str = "",
         delai: int = 20) -> str:
    auth = f"-H 'Authorization: Bearer {jeton}'" if jeton else ""
    lang = f"-H 'Accept-Language: {langue}'" if langue else ""
    return poste.run(
        f"curl -s --max-time {delai} {auth} {lang} http://{ip}/{chemin.lstrip('/')}"
    ).stdout


def _commandes(edge) -> int:
    brut = edge.run(f"sudo cat {COMPTEUR}").stdout.strip()
    try:
        return int(json.loads(brut).get("commandes", -1))
    except (json.JSONDecodeError, AttributeError, ValueError):
        return -1


def test_une_reponse_eligible_est_reutilisee_avec_sa_variation(
    poste, ip_edge
) -> None:
    """Le cache sert deux fois la même réponse, ET il ne sert plus le privé.

    `/public` porte un numéro tiré au hasard à chaque passage côté
    application : deux réponses identiques prouvent donc un cache, et deux
    réponses différentes prouvent qu'il n'y en a pas. Aucune en-tête à
    croire sur parole.

    POURQUOI LA SECONDE MOITIÉ EST LÀ

    L'état de départ met déjà en cache et varie déjà sur la langue : sans
    elle, ce test passait avant tout travail, et le lab donnait 25 points
    sur 100 à qui n'avait rien fait. Mesuré le 2026-10-26.

    Ce que la fiche demande n'est pas « mettre en cache », qui est déjà
    fait, mais « mettre en cache SANS partager ce qui est privé ». Les deux
    moitiés séparément sont triviales : ne rien cacher satisfait la
    seconde, tout cacher satisfait la première. C'est leur rencontre qui
    est le travail.
    """
    premier = _get(poste, ip_edge, "/public", langue="fr")
    second = _get(poste, ip_edge, "/public", langue="fr")
    assert premier.strip() and premier == second, message(
        en=(
            "Two identical requests to /public returned two different bodies: "
            f"nothing is being cached ({premier.strip()[:40]!r} then "
            f"{second.strip()[:40]!r})."
        ),
        fr=(
            "Deux requêtes identiques sur /public ont rendu deux corps "
            f"différents : rien n'est mis en cache ({premier.strip()[:40]!r} "
            f"puis {second.strip()[:40]!r})."
        ),
    )

    autre_langue = _get(poste, ip_edge, "/public", langue="en")
    assert autre_langue != premier, message(
        en=(
            "A request in another language got the cached French answer. The "
            "cache does not vary on the header that changes the content: "
            "declare it under `cache.varier_sur`."
        ),
        fr=(
            "Une requête dans une autre langue a reçu la réponse française "
            "mise en cache. Le cache ne varie pas sur l'en-tête qui change le "
            "contenu : déclarez-le sous `cache.varier_sur`."
        ),
    )

    # Et le cache ne sert plus ce qui est privé. C'est ce qui distingue une
    # politique corrigée d'une politique rapide et dangereuse : les deux
    # accélèrent, une seule est utilisable.
    prive_un = _get(poste, ip_edge, "/prive", jeton="alice")
    prive_deux = _get(poste, ip_edge, "/prive", jeton="bob")
    assert prive_un.strip() and prive_un != prive_deux, message(
        en=(
            "Two different accounts received the SAME private body "
            f"({prive_un.strip()[:50]!r}). Caching is not the achievement "
            "here: the starting policy already caches, and already varies on "
            "language. The achievement is caching without sharing what is "
            "private."
        ),
        fr=(
            "Deux comptes différents ont reçu le MÊME corps privé "
            f"({prive_un.strip()[:50]!r}). Mettre en cache n'est pas "
            "l'accomplissement ici : la politique de départ met déjà en cache, "
            "et varie déjà sur la langue. L'accomplissement est de mettre en "
            "cache sans partager ce qui est privé."
        ),
    )


def test_une_donnee_privee_n_est_jamais_servie_a_l_autre(poste, ip_edge) -> None:
    """CRITIQUE. Alice ne reçoit jamais les données de Bob, ni l'inverse.

    Les deux appels se suivent immédiatement : c'est la fenêtre où un cache
    mal réglé sert la réponse du premier au second.
    """
    chez_alice = _get(poste, ip_edge, "/prive", jeton=ALICE)
    chez_bob = _get(poste, ip_edge, "/prive", jeton=BOB)

    assert "ALICE" in chez_alice, message(
        en=f"Alice did not get her own data: {chez_alice.strip()[:80]!r}.",
        fr=f"Alice n'a pas reçu ses propres données : {chez_alice.strip()[:80]!r}.",
    )
    assert "ALICE" not in chez_bob, message(
        en=(
            "Bob received Alice's private data. A private answer must never be "
            "cached under a key that does not distinguish the user: either "
            "keep the route out of `cache.cacher`, or vary on the identity."
        ),
        fr=(
            "Bob a reçu les données privées d'Alice. Une réponse privée ne doit "
            "jamais être mise en cache sous une clé qui ne distingue pas "
            "l'utilisateur : sortez la route de `cache.cacher`, ou variez sur "
            "l'identité."
        ),
    )
    assert "BOB" in chez_bob, message(
        en=f"Bob did not get his own data either: {chez_bob.strip()[:80]!r}.",
        fr=f"Bob n'a pas reçu ses propres données non plus : {chez_bob.strip()[:80]!r}.",
    )


def test_une_action_non_idempotente_n_est_pas_dupliquee(
    poste, edge, ip_edge
) -> None:
    """CRITIQUE. Une commande perdue en route ne doit pas être passée deux fois.

    L'application incrémente le compteur puis coupe sans répondre. Le client
    ne peut pas distinguer « rien n'a eu lieu » de « tout a eu lieu, la
    réponse s'est perdue ». Rejouer dans le doute double la commande, et le
    compteur est le seul endroit où cela se voit.
    """
    avant = _commandes(edge)
    assert avant >= 0, message(
        en=f"The business counter could not be read in {COMPTEUR}.",
        fr=f"Le compteur métier n'a pas pu être lu dans {COMPTEUR}.",
    )

    poste.run(f"curl -s --max-time 20 -X POST http://{ip_edge}/commande")
    time.sleep(2)
    apres = _commandes(edge)

    assert apres == avant + 1, message(
        en=(
            f"One order was sent and the counter moved from {avant} to {apres}. "
            + (
                "It was replayed: a POST whose answer was lost must not be "
                "retried, because the caller cannot tell a lost answer from an "
                "action that never happened. Remove POST from "
                "`tentatives.rejouer`."
                if apres > avant + 1
                else "It was not recorded at all, which is a different failure."
            )
        ),
        fr=(
            f"Une commande a été envoyée et le compteur est passé de {avant} à "
            f"{apres}. "
            + (
                "Elle a été rejouée : un POST dont la réponse s'est perdue ne "
                "doit pas être réessayé, parce que l'appelant ne distingue pas "
                "une réponse perdue d'une action qui n'a pas eu lieu. Retirez "
                "POST de `tentatives.rejouer`."
                if apres > avant + 1
                else "Elle n'a pas été enregistrée du tout, ce qui est un autre "
                     "défaut."
            )
        ),
    )


def test_la_lenteur_attendue_passe_et_la_panne_est_bornee(poste, ip_edge) -> None:
    """La borne admet les deux secondes de `/lent` et coupe `/panne`.

    Les deux moitiés comptent. Une borne trop courte rejette une réponse
    lente mais correcte, et c'est une panne qu'on s'inflige. Une borne
    absente laisse l'appelant attendre indéfiniment, et c'est la panne qui se
    propage.
    """
    debut = time.monotonic()
    lent = _get(poste, ip_edge, "/lent", delai=30)
    duree_lent = time.monotonic() - debut
    assert "LENT" in lent, message(
        en=(
            f"/lent did not answer in {duree_lent:.1f} s, although the backend "
            "takes two seconds. The read timeout is shorter than a legitimate "
            "answer: a bound that rejects what works is a self-inflicted "
            "outage."
        ),
        fr=(
            f"/lent n'a pas répondu en {duree_lent:.1f} s, alors que le backend "
            "met deux secondes. La borne de lecture est plus courte qu'une "
            "réponse légitime : une limite qui rejette ce qui marche est une "
            "panne qu'on s'inflige."
        ),
    )

    debut = time.monotonic()
    poste.run(f"curl -s -o /dev/null --max-time 25 http://{ip_edge}/panne")
    duree_panne = time.monotonic() - debut
    assert duree_panne < 20, message(
        en=(
            f"/panne held the caller for {duree_panne:.0f} s. A backend that "
            "never answers must be given up on: declare `delais.lecture` so "
            "the failure stays on this side instead of spreading to every "
            "caller."
        ),
        fr=(
            f"/panne a retenu l'appelant {duree_panne:.0f} s. Un backend qui ne "
            "répond jamais doit être abandonné : déclarez `delais.lecture` pour "
            "que la panne reste de ce côté au lieu de se propager à tous les "
            "appelants."
        ),
    )
