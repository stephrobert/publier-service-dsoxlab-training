"""Verify that every name and path reaches the intended backend, that an
unexpected name reaches none, that the map really decides and loses a runtime
change on reload, and that the dossier covers the two undecidable cases.

CE QUE LE SETUP POSE : HAProxy en service, quatre backends sains, un socket
d'administration, et une table de routage fausse de quatre façons.

CE QUI MESURE, ET POURQUOI CE N'EST PAS LA REPONSE RENDUE

Chaque backend compte les requêtes qu'il sert. La validation lit ces
compteurs avant et après chaque requête, et exige que le delta soit de 1 chez
le backend attendu et de 0 partout ailleurs.

Sans cela, ce lab ne serait pas mesurable. Un `default_backend panier` répond
200 avec un corps plausible pour n'importe quel nom : la réponse ne dit pas
quel backend l'a produite. Lire le corps suffirait, puisque chaque service
donne son nom — mais seulement tant que l'apprenant ne remplace pas une route
par un `http-request return`. Le compteur, lui, ne peut être bougé que par une
requête réellement servie.
"""

from __future__ import annotations

import time
import uuid

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-routage/recette.txt"
MARQUE = "pub-haproxy-routage service"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _lignes(edge, cle: str) -> list[str]:
    sortie = edge.run(f"grep -oP '(?<=^{cle} = ).*' {RECETTE}").stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def _valeur(edge, cle: str) -> str:
    lues = _lignes(edge, cle)
    assert len(lues) == 1, message(
        en=f"The recipe {RECETTE} declares {len(lues)} `{cle}`, expected one.",
        fr=f"La recette {RECETTE} déclare {len(lues)} `{cle}`, on en attend un.",
    )
    return lues[0]


@pytest.fixture(scope="module")
def ports(edge) -> dict[str, int]:
    """Les ports des compteurs, lus dans la recette et non écrits en dur."""
    table: dict[str, int] = {}
    for ligne in _lignes(edge, "compteur"):
        nom, port = ligne.split()
        table[nom] = int(port)
    assert table, message(
        en=f"The recipe {RECETTE} declares no counter.",
        fr=f"La recette {RECETTE} ne déclare aucun compteur.",
    )
    return table


def _compteurs(edge, ports: dict[str, int]) -> dict[str, int]:
    """Lit les quatre compteurs en UNE commande.

    `curl` accepte plusieurs URL et rend leurs corps dans l'ordre. Quatre
    appels séparés coûteraient quatre allers-retours par mesure, soit plus de
    cent pour la seule matrice, et la mesure deviendrait assez lente pour
    qu'on soit tenté de l'alléger.
    """
    noms = list(ports)
    urls = " ".join(f"http://127.0.0.1:{ports[n]}/__compteur" for n in noms)
    sortie = edge.run(f"curl -s --max-time 5 {urls}").stdout.split()
    assert len(sortie) == len(noms), message(
        en=(
            f"Expected {len(noms)} counters, read {len(sortie)}: at least one "
            "backend of the lab is not answering."
        ),
        fr=(
            f"On attend {len(noms)} compteurs, {len(sortie)} lus : au moins un "
            "backend du lab ne répond pas."
        ),
    )
    return {nom: int(valeur) for nom, valeur in zip(noms, sortie, strict=True)}


def _demander(poste, ip: str, hote: str, chemin: str) -> tuple[str, str]:
    """Une requête depuis le client, avec un jeton propre à la mesure.

    Le jeton part en chaîne de requête, que HAProxy ne compte pas dans
    `path` : il rend la ligne de journal reconnaissable sans changer la
    décision de routage.
    """
    jeton = uuid.uuid4().hex[:10]
    separateur = "&" if "?" in chemin else "?"
    cible = f"http://{ip}{chemin}{separateur}jeton={jeton}"
    sortie = poste.run(
        f"curl -s -o /tmp/corps -w '%{{http_code}}' --max-time 10 "
        f"-H 'Host: {hote}' '{cible}'"
    ).stdout.strip()
    corps = poste.run("cat /tmp/corps").stdout
    return sortie, corps


def _mesurer(edge, poste, ip: str, ports, hote: str, chemin: str):
    avant = _compteurs(edge, ports)
    statut, corps = _demander(poste, ip, hote, chemin)
    apres = _compteurs(edge, ports)
    deltas = {nom: apres[nom] - avant[nom] for nom in ports}
    return statut, corps, deltas


def test_chaque_nom_et_chemin_atteint_le_backend_prevu(
    edge, poste, ip_edge, ports
) -> None:
    """La matrice, chemins voisins compris, et mesurée chez les backends."""
    attendus = _lignes(edge, "attendu")
    assert attendus, message(
        en=f"The recipe {RECETTE} declares no expected route.",
        fr=f"La recette {RECETTE} ne déclare aucune route attendue.",
    )

    for ligne in attendus:
        hote, chemin, voulu = ligne.split()
        statut, corps, deltas = _mesurer(
            edge, poste, ip_edge, ports, hote, chemin
        )
        bouges = {nom: d for nom, d in deltas.items() if d != 0}

        if voulu == "refus":
            assert statut in ("403", "404"), message(
                en=(
                    f"Host {hote} path {chemin} answered {statut}, expected 403 "
                    "or 404: the recipe refuses this route."
                ),
                fr=(
                    f"Host {hote} chemin {chemin} a répondu {statut}, on attend "
                    "403 ou 404 : la recette refuse cette route."
                ),
            )
            assert not bouges, message(
                en=(
                    f"Host {hote} path {chemin} was refused, but reached "
                    f"{sorted(bouges)}. A refusal that still touches a backend "
                    "is a route, not a refusal: the rule that refuses must come "
                    "before the one that routes."
                ),
                fr=(
                    f"Host {hote} chemin {chemin} a été refusé, mais a atteint "
                    f"{sorted(bouges)}. Un refus qui touche quand même un "
                    "backend est une route, pas un refus : la règle qui refuse "
                    "doit passer avant celle qui route."
                ),
            )
            continue

        assert statut == "200", message(
            en=f"Host {hote} path {chemin} answered {statut}, expected 200.",
            fr=f"Host {hote} chemin {chemin} a répondu {statut}, on attend 200.",
        )
        assert bouges == {voulu: 1}, message(
            en=(
                f"Host {hote} path {chemin} should reach {voulu} and nothing "
                f"else. Counters moved: {bouges or 'none'}. Answer started "
                f"with {corps.strip()[:80]!r}."
            ),
            fr=(
                f"Host {hote} chemin {chemin} doit atteindre {voulu} et rien "
                f"d'autre. Compteurs bougés : {bouges or 'aucun'}. La réponse "
                f"commençait par {corps.strip()[:80]!r}."
            ),
        )
        assert f"{MARQUE} {voulu}" in corps, message(
            en=(
                f"{voulu} counted the request but the answer does not come from "
                f"it ({corps.strip()[:80]!r})."
            ),
            fr=(
                f"{voulu} a compté la requête mais la réponse ne vient pas de "
                f"lui ({corps.strip()[:80]!r})."
            ),
        )


def test_un_nom_imprevu_n_atteint_aucun_backend(edge, poste, ip_edge, ports) -> None:
    """CRITIQUE : les noms sans route ne tombent sur rien.

    Les noms sont tirés au hasard à chaque exécution. Une liste écrite dans
    le test se ferait traiter nommément, ce qui n'est pas la propriété qu'on
    veut : on veut que TOUT nom absent de la table soit refusé, et un nom
    qu'on ne peut pas prévoir est la seule façon de le mesurer.

    Ce test ne tire pas de CHEMIN au hasard, et c'est volontaire : la table
    donne à chaque nom connu une route par défaut, donc un chemin imprévu
    sous un nom connu est légitimement routé. Mélanger les deux reviendrait
    à exiger une propriété que la recette ne demande pas.
    """
    for _ in range(5):
        hote = f"{uuid.uuid4().hex[:12]}.imprevu.test"
        statut, _corps, deltas = _mesurer(edge, poste, ip_edge, ports, hote, "/")
        bouges = {nom: d for nom, d in deltas.items() if d != 0}
        assert statut in ("403", "404"), message(
            en=(
                f"The unknown name {hote} answered {statut}. A name with no "
                "route must be refused, not served by whichever backend the "
                "default points at."
            ),
            fr=(
                f"Le nom inconnu {hote} a répondu {statut}. Un nom sans route "
                "doit être refusé, pas servi par le backend que désigne le "
                "défaut."
            ),
        )
        assert not bouges, message(
            en=(
                f"The unknown name {hote} reached {sorted(bouges)}. This is the "
                "leaking route the lab is about: a default backend serves names "
                "a third party chooses, and the answer it returns looks normal."
            ),
            fr=(
                f"Le nom inconnu {hote} a atteint {sorted(bouges)}. C'est la "
                "route de fuite dont parle ce lab : un backend par défaut sert "
                "des noms qu'un tiers choisit, et la réponse qu'il rend a l'air "
                "normale."
            ),
        )

    # Et le chemin nommement refuse, sous un nom connu, avec une suite tiree
    # au hasard : refuser `/api/v2/etat` seul serait refuser un chemin, pas
    # une branche.
    for _ in range(3):
        chemin = f"/api/v2/{uuid.uuid4().hex[:8]}"
        statut, _corps, deltas = _mesurer(
            edge, poste, ip_edge, ports, "admin.pub.lab.test", chemin
        )
        bouges = {nom: d for nom, d in deltas.items() if d != 0}
        assert statut in ("403", "404") and not bouges, message(
            en=(
                f"{chemin} answered {statut} and reached {sorted(bouges) or 'nothing'}. "
                "The recipe refuses the whole /api/v2/ branch, not just the one "
                "path it names."
            ),
            fr=(
                f"{chemin} a répondu {statut} et a atteint "
                f"{sorted(bouges) or 'rien'}. La recette refuse toute la branche "
                "/api/v2/, pas seulement le chemin qu'elle nomme."
            ),
        )


def test_la_table_se_change_a_chaud_et_ne_survit_pas_au_rechargement(
    edge, poste, ip_edge, ports
) -> None:
    """Les deux moitiés : la map décide, et le fichier fait foi.

    La première prouve que la map est dans le chemin de décision, au lieu
    d'être un fichier décoratif à côté d'ACL qui tranchent vraiment. La
    seconde est la raison pour laquelle un changement à chaud se recopie
    toujours dans le fichier.
    """
    carte = _valeur(edge, "map_noms")
    socket = _valeur(edge, "socket_admin")

    def piloter(commande: str) -> str:
        return edge.run(f"echo '{commande}' | sudo socat -t2 stdio {socket}").stdout

    tables = piloter("show map")
    assert carte in tables, message(
        en=(
            f"`show map` does not list {carte} (answer: {tables.strip()[:160]!r}). "
            "The recipe asks for the name table to be a map, loaded by HAProxy."
        ),
        fr=(
            f"`show map` ne liste pas {carte} (réponse : {tables.strip()[:160]!r}). "
            "La recette demande que la table des noms soit une map, chargée par "
            "HAProxy."
        ),
    )

    entree = piloter(f"get map {carte} boutique.pub.lab.test")
    assert "vitrine" in entree, message(
        en=(
            "The map does not map boutique.pub.lab.test to vitrine "
            f"(answer: {entree.strip()[:160]!r})."
        ),
        fr=(
            "La map n'associe pas boutique.pub.lab.test à vitrine "
            f"(réponse : {entree.strip()[:160]!r})."
        ),
    )

    piloter(f"set map {carte} boutique.pub.lab.test console")
    try:
        statut, _corps, deltas = _mesurer(
            edge, poste, ip_edge, ports, "boutique.pub.lab.test", "/"
        )
        bouges = {nom: d for nom, d in deltas.items() if d != 0}
        assert statut == "200" and bouges == {"console": 1}, message(
            en=(
                "After `set map boutique.pub.lab.test console`, the request "
                f"answered {statut} and moved {bouges or 'nothing'}, expected "
                "console. The map is loaded but does not decide: an ACL placed "
                "before it is settling the name, and the map is decoration."
            ),
            fr=(
                "Après `set map boutique.pub.lab.test console`, la requête a "
                f"répondu {statut} et bougé {bouges or 'rien'}, on attend "
                "console. La map est chargée mais ne décide pas : une ACL placée "
                "avant elle tranche le nom, et la map est décorative."
            ),
        )

        # ET LA MOITIE QUI DISTINGUE CE TEST DE L'ETAT DE DEPART.
        #
        # Dans l'etat de depart, la ligne qui consulte la map est DEJA la
        # premiere regle : le changement a chaud y fonctionne donc sans
        # qu'on ait rien corrige, et ce test donnait 25/100 gratuitement.
        # Mesure du 2026-10-26.
        #
        # Une exception de chemin doit l'emporter sur la table : avec la map
        # detournee vers console, `/panier` sous boutique doit TOUJOURS
        # atteindre le panier. C'est faux dans l'etat de depart, ou la map
        # passe avant, et vrai une fois l'ordre corrige.
        statut, _corps, deltas = _mesurer(
            edge, poste, ip_edge, ports, "boutique.pub.lab.test", "/panier"
        )
        bouges = {nom: d for nom, d in deltas.items() if d != 0}
        assert statut == "200" and bouges == {"panier": 1}, message(
            en=(
                "With the name table diverted to console, "
                "boutique.pub.lab.test/panier answered "
                f"{statut} and moved {bouges or 'nothing'}, expected panier. A "
                "path exception must outrank the table: the table is the "
                "default of a name, not its only rule. If the exception loses, "
                "the line that consults the map comes before it."
            ),
            fr=(
                "La table des noms étant détournée vers console, "
                "boutique.pub.lab.test/panier a répondu "
                f"{statut} et bougé {bouges or 'rien'}, on attend panier. Une "
                "exception de chemin doit l'emporter sur la table : la table "
                "est le défaut d'un nom, pas sa seule règle. Si l'exception "
                "perd, c'est que la ligne qui consulte la map passe avant elle."
            ),
        )
    finally:
        # Le rechargement est AUSSI la remise en etat : c'est ce qui rend ce
        # nettoyage honnete, puisqu'il est le geste que le test mesure.
        edge.run("sudo systemctl reload haproxy")

    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        if "LISTEN" in edge.run("ss -ltn 'sport = :80'").stdout:
            break
        time.sleep(1)

    statut, _corps, deltas = _mesurer(
        edge, poste, ip_edge, ports, "boutique.pub.lab.test", "/"
    )
    bouges = {nom: d for nom, d in deltas.items() if d != 0}
    assert statut == "200" and bouges == {"vitrine": 1}, message(
        en=(
            f"After the reload, the request answered {statut} and moved "
            f"{bouges or 'nothing'}, expected vitrine. A runtime change to a map "
            "lives in memory only: the reload reloads the FILE. If the routing "
            "did not come back, the runtime change was written into the file, "
            "and the file no longer says what the recipe asks."
        ),
        fr=(
            f"Après le rechargement, la requête a répondu {statut} et bougé "
            f"{bouges or 'rien'}, on attend vitrine. Un changement à chaud dans "
            "une map ne vit qu'en mémoire : le rechargement relit le FICHIER. Si "
            "le routage n'est pas revenu, c'est que le changement à chaud a été "
            "écrit dans le fichier, et le fichier ne dit plus ce que la recette "
            "demande."
        ),
    )


def test_le_dossier_traite_les_deux_cas_indecidables(edge) -> None:
    """Le dossier existe et couvre les deux cas qu'on ne tranche qu'en regardant.

    CE QUE CE TEST NE FAIT PAS : juger le raisonnement. Un humain relit le
    dossier, et c'est lui qui dira si l'explication tient. Un test qui
    prétendrait noter une explication noterait en réalité la présence de
    mots-clés, ce qui apprend à écrire des mots-clés.
    """
    chemin = _valeur(edge, "dossier")
    contenu = edge.run(f"cat {chemin} 2>/dev/null").stdout
    assert contenu.strip(), message(
        en=(
            f"{chemin} is missing or empty. The recipe asks for a dossier that "
            "explains the order of the decisions and the ambiguity you fixed."
        ),
        fr=(
            f"{chemin} est absent ou vide. La recette demande un dossier qui "
            "explique l'ordre des décisions et l'ambiguïté corrigée."
        ),
    )
    assert len(contenu) >= 400, message(
        en=(
            f"{chemin} holds {len(contenu)} characters. The two cases to settle "
            "need more than a line each."
        ),
        fr=(
            f"{chemin} porte {len(contenu)} caractères. Les deux cas à trancher "
            "demandent plus d'une ligne chacun."
        ),
    )

    for sujet, motifs in (
        ("les chemins voisins de /panier", ("panierarchive", "panier-public")),
        ("la branche /api/v2/", ("/api/v2", "api/v2")),
    ):
        assert any(motif in contenu for motif in motifs), message(
            en=(
                f"{chemin} does not mention {sujet}. These are the two cases no "
                "rule settles by itself: a prefix that catches a neighbour, and "
                "a branch that must be refused rather than routed."
            ),
            fr=(
                f"{chemin} ne traite pas {sujet}. Ce sont les deux cas qu'aucune "
                "règle ne tranche d'elle-même : un préfixe qui attrape un voisin, "
                "et une branche qu'il faut refuser plutôt que router."
            ),
        )
