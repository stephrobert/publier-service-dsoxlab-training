"""Verify that the table counts the client's address over the declared window,
that overrun refuses without blocking anyone else, that the key cannot be
chosen by the client and that the block lifts, and that the declared memory
bounds hold.

CE QUE LE SETUP POSE : une stick-table qui se remplit, se lit, et ne protege
de rien : cle fournie par le client, seuil hors d'atteinte, fenetre et
expiration confondues.

LES DEUX BORNES DE TEMPS, ET POURQUOI ELLES SONT MESUREES SEPAREMENT

`http_req_rate(<fenetre>)` dit sur combien de temps la cadence est calculee.
`expire` dit combien de temps une entree survit a sa derniere requete. Les
confondre donne une configuration qui a l'air juste et qui ne mesure pas ce
qu'on croit : avec une expiration plus courte que la fenetre, l'entree
disparait avant que la cadence ait fini d'etre calculee, et le compteur
repart de zero sans que rien ne le dise.

Le premier controle mesure la fenetre, en exigeant que la cadence retombe a
zero apres elle. Le quatrieme mesure l'expiration, en exigeant que l'entree
DISPARAISSE apres elle. Les deux mesures seraient satisfaites par une seule
valeur, et c'est pour cela qu'elles portent sur des grandeurs differentes :
une cadence nulle n'est pas une entree absente.
"""

from __future__ import annotations

import re
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-stick-tables/recette.txt"
MARQUE = "pub-haproxy-stick-tables service"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


@pytest.fixture(scope="module")
def ip_poste():
    return lab_host_ip(CLIENT)


def _valeur(edge, cle: str) -> str:
    valeur = edge.run(f"grep -oP '(?<=^{cle} = ).*' {RECETTE}").stdout.strip()
    assert valeur, message(
        en=f"The recipe {RECETTE} declares no `{cle}`.",
        fr=f"La recette {RECETTE} ne déclare aucun `{cle}`.",
    )
    return valeur


@pytest.fixture(scope="module")
def recette(edge) -> dict[str, str]:
    cles = (
        "table",
        "fenetre",
        "expiration",
        "seuil",
        "statut_refus",
        "taille",
        "dossier",
        "socket_admin",
    )
    return {cle: _valeur(edge, cle) for cle in cles}


def _table(edge, recette) -> str:
    return edge.run(
        f"echo 'show table {recette['table']}' "
        f"| sudo socat -t3 stdio {recette['socket_admin']}"
    ).stdout


def _entree(edge, recette, cle: str) -> dict[str, str] | None:
    """La ligne de la table pour une clé, décomposée en champs.

    Rend None quand la clé n'est PAS dans la table, ce qui est une réponse
    distincte d'une cadence nulle : c'est sur cette distinction que repose la
    mesure de l'expiration.
    """
    for ligne in _table(edge, recette).splitlines():
        champs: dict[str, str] = {}
        for morceau in ligne.split():
            if "=" in morceau:
                nom, valeur = morceau.split("=", 1)
                champs[nom] = valeur
        # On compare le CHAMP `key`, et non la presence de la chaine dans la
        # ligne : `key=10.0.0.1` est contenu dans `key=10.0.0.10`, et une
        # recherche de sous-chaine rendrait l'entree d'un voisin.
        if champs.get("key") == cle:
            return champs
    return None


def _cadence(champs: dict[str, str]) -> int:
    for nom, valeur in champs.items():
        if nom.startswith("http_req_rate"):
            return int(valeur)
    return -1


def _rafale(poste, ip: str, nombre: int, entete: str | None = None) -> dict[str, int]:
    supplement = f" {entete}" if entete else ""
    sortie = poste.run(f"rafale {ip} {nombre}{supplement}").stdout
    comptes: dict[str, int] = {}
    for ligne in sortie.splitlines():
        if ligne.strip():
            cle, compte = ligne.rsplit(" ", 1)
            comptes[cle] = int(compte)
    return comptes


def _attendre_absence(edge, recette, cle: str, limite_s: float) -> bool:
    limite = time.monotonic() + limite_s
    while time.monotonic() < limite:
        if _entree(edge, recette, cle) is None:
            return True
        time.sleep(2)
    return False


def test_la_table_compte_l_adresse_du_client_sur_la_fenetre_annoncee(
    edge, poste, recette, ip_edge, ip_poste
) -> None:
    """La clé est l'adresse, la cadence est le compte, et la fenêtre se mesure."""
    # On repart d'une table vide pour cette cle : une mesure de cadence qui
    # commence sur un compteur deja charge ne mesure rien.
    _attendre_absence(
        edge, recette, ip_poste, int(recette["expiration"]) + 10
    )

    envoyees = 5
    comptes = _rafale(poste, ip_edge, envoyees)
    assert comptes.get("200") == envoyees, message(
        en=f"{envoyees} requests under the threshold gave {comptes}, expected all 200.",
        fr=f"{envoyees} requêtes sous le seuil ont donné {comptes}, on attend 200 partout.",
    )

    champs = _entree(edge, recette, ip_poste)
    assert champs is not None, message(
        en=(
            f"The table {recette['table']} has no entry keyed on the client's "
            f"address {ip_poste}. The recipe asks for the client's ADDRESS to be "
            "counted, not a value it supplies: a client that can pick its key "
            f"can pick its counter. Table:\n{_table(edge, recette)[:400]}"
        ),
        fr=(
            f"La table {recette['table']} ne porte aucune entrée clavée sur "
            f"l'adresse du client {ip_poste}. La recette demande de compter "
            "l'ADRESSE du client, pas une valeur qu'il fournit : un client qui "
            "peut choisir sa clé peut choisir son compteur. Table :\n"
            f"{_table(edge, recette)[:400]}"
        ),
    )

    cadence = _cadence(champs)
    assert cadence == envoyees, message(
        en=(
            f"The table reports a rate of {cadence} after {envoyees} requests. "
            f"Entry: {champs}."
        ),
        fr=(
            f"La table annonce une cadence de {cadence} après {envoyees} "
            f"requêtes. Entrée : {champs}."
        ),
    )

    # LA FENETRE, mesuree et non lue. Apres elle, la cadence retombe a zero
    # alors que l'entree est TOUJOURS LA : c'est ce qui distingue la fenetre
    # de l'expiration.
    time.sleep(int(recette["fenetre"]) + 3)
    champs = _entree(edge, recette, ip_poste)
    assert champs is not None, message(
        en=(
            f"The entry for {ip_poste} disappeared {recette['fenetre']}s after "
            f"the last request, while the recipe declares an expiry of "
            f"{recette['expiration']}s. The window and the expiry are being "
            "confused: one is how long the rate is measured over, the other how "
            "long the entry survives."
        ),
        fr=(
            f"L'entrée de {ip_poste} a disparu {recette['fenetre']} s après la "
            f"dernière requête, alors que la recette déclare une expiration de "
            f"{recette['expiration']} s. La fenêtre et l'expiration sont "
            "confondues : l'une dit sur combien de temps la cadence est mesurée, "
            "l'autre combien de temps l'entrée survit."
        ),
    )
    assert _cadence(champs) == 0, message(
        en=(
            f"The rate is still {_cadence(champs)} more than "
            f"{recette['fenetre']}s after the last request. The window declared "
            "in the recipe is not the one in use."
        ),
        fr=(
            f"La cadence vaut encore {_cadence(champs)} plus de "
            f"{recette['fenetre']} s après la dernière requête. La fenêtre "
            "déclarée dans la recette n'est pas celle en service."
        ),
    )


def test_le_depassement_refuse_et_seul_le_depassement(
    edge, poste, recette, ip_edge, ip_poste
) -> None:
    """La rafale au seuil passe, l'au-delà refuse, et l'autre source est servie."""
    _attendre_absence(edge, recette, ip_poste, int(recette["expiration"]) + 10)

    seuil = int(recette["seuil"])
    comptes = _rafale(poste, ip_edge, seuil)
    assert comptes.get("200") == seuil, message(
        en=(
            f"A burst of exactly {seuil} requests gave {comptes}. The recipe's "
            "threshold is inclusive: a control stricter than what was asked is "
            "also a fault, because it refuses traffic the service was sized for."
        ),
        fr=(
            f"Une rafale de {seuil} requêtes exactement a donné {comptes}. Le "
            "seuil de la recette est inclusif : un contrôle plus strict que ce "
            "qui est demandé est aussi une faute, puisqu'il refuse du trafic pour "
            "lequel le service est dimensionné."
        ),
    )

    au_dela = _rafale(poste, ip_edge, 5)
    refus = recette["statut_refus"]
    assert au_dela.get(refus, 0) >= 1, message(
        en=(
            f"Beyond the threshold, the answers were {au_dela}, with no {refus}. "
            "The deny rule exists in the starting state and never fires: its "
            "threshold is out of reach."
        ),
        fr=(
            f"Au-delà du seuil, les réponses ont été {au_dela}, sans aucun "
            f"{refus}. La règle de refus existe dans l'état de départ et ne se "
            "déclenche jamais : son seuil est hors d'atteinte."
        ),
    )

    # REPRODUCTIBLE : un refus qui depend du hasard n'est pas une politique.
    for essai in range(3):
        encore = _rafale(poste, ip_edge, 3)
        assert encore.get(refus, 0) == 3, message(
            en=(
                f"Replay {essai + 1} of the overrun gave {encore}, expected three "
                f"{refus}. A refusal that depends on luck is not a policy."
            ),
            fr=(
                f"Le rejeu {essai + 1} du dépassement a donné {encore}, on attend "
                f"trois {refus}. Un refus qui dépend du hasard n'est pas une "
                "politique."
            ),
        )

    # L'AUTRE SOURCE EST SERVIE. Sans cette mesure, un `http-request deny`
    # inconditionnel passerait tout ce qui precede : il refuse aussi, et
    # reproductiblement.
    depuis_la_machine = edge.run(
        "curl -s --max-time 10 http://127.0.0.1/"
    ).stdout
    assert MARQUE in depuis_la_machine, message(
        en=(
            "While one source is refused, another source is refused too "
            f"({depuis_la_machine.strip()[:160]!r}). The limit does not protect "
            "the service then, it replaces it. The counter is per key, so the "
            "refusal must be too."
        ),
        fr=(
            "Pendant qu'une source est refusée, une autre source l'est aussi "
            f"({depuis_la_machine.strip()[:160]!r}). La limite ne protège pas le "
            "service, elle le remplace. Le compteur est par clé, donc le refus "
            "doit l'être aussi."
        ),
    )


def test_la_cle_ne_peut_pas_etre_choisie_par_le_client(
    edge, poste, recette, ip_edge, ip_poste
) -> None:
    """CRITIQUE : changer d'en-tête ne donne pas un compteur neuf.

    Et la moitié qui compte : le blocage se lève. Un blocage qui ne se lève
    pas n'est pas une limite de cadence, c'est un bannissement, et une
    adresse bannie par erreur se rouvre à la main, donc jamais.
    """
    refus = recette["statut_refus"]
    seuil = int(recette["seuil"])

    _attendre_absence(edge, recette, ip_poste, int(recette["expiration"]) + 10)
    _rafale(poste, ip_edge, seuil + 5)

    bloque = _rafale(poste, ip_edge, 2)
    assert bloque.get(refus, 0) == 2, message(
        en=f"The source is not refused before the measurement starts: {bloque}.",
        fr=f"La source n'est pas refusée avant le début de la mesure : {bloque}.",
    )

    for valeur in ("neuf", "autre", "x" * 40, "1.2.3.4", ip_poste):
        comptes = _rafale(poste, ip_edge, 2, valeur)
        assert comptes.get(refus, 0) == 2, message(
            en=(
                f"With X-Client-Id: {valeur!r}, the refused source was served "
                f"again ({comptes}). The key must not be something the client "
                "sends: a header is chosen by whoever sends it, so a counter "
                "keyed on it is reset by whoever it was meant to limit."
            ),
            fr=(
                f"Avec X-Client-Id: {valeur!r}, la source refusée a été servie à "
                f"nouveau ({comptes}). La clé ne doit pas être une valeur que le "
                "client envoie : un en-tête est choisi par celui qui l'envoie, "
                "donc un compteur clavé dessus est remis à zéro par celui même "
                "qu'il devait limiter."
            ),
        )

    # LE BLOCAGE SE LEVE. On attend la fenetre, pas l'expiration : la cadence
    # retombe sous le seuil des que la fenetre a passe, meme si l'entree vit
    # encore.
    time.sleep(int(recette["fenetre"]) + 3)
    revenu = _rafale(poste, ip_edge, 2)
    assert revenu.get("200", 0) == 2, message(
        en=(
            f"{int(recette['fenetre']) + 3}s after the overrun, the source is "
            f"still refused ({revenu}). A block that does not lift is a ban, not "
            "a rate limit: an address banned by mistake is reopened by hand, "
            "which means never."
        ),
        fr=(
            f"{int(recette['fenetre']) + 3} s après le dépassement, la source est "
            f"encore refusée ({revenu}). Un blocage qui ne se lève pas est un "
            "bannissement, pas une limite de cadence : une adresse bannie par "
            "erreur se rouvre à la main, donc jamais."
        ),
    )


def test_les_bornes_de_memoire_sont_celles_annoncees(
    edge, poste, recette, ip_edge, ip_poste
) -> None:
    """La taille déclarée, et l'expiration MESURÉE sur la disparition.

    Une cadence nulle n'est pas une entrée absente. Les deux mesures seraient
    satisfaites par une seule valeur, et c'est pour cela que celle-ci porte
    sur la disparition : c'est la seule qui dit ce que la table occupe
    réellement en mémoire.
    """
    entete = _table(edge, recette).splitlines()[0]
    taille = re.search(r"size:(\d+)", entete)
    assert taille, message(
        en=f"`show table {recette['table']}` does not report a size: {entete!r}",
        fr=f"`show table {recette['table']}` ne rapporte pas de taille : {entete!r}",
    )
    assert taille.group(1) == recette["taille"], message(
        en=(
            f"The table declares size {taille.group(1)}, the recipe asks for "
            f"{recette['taille']}. The size bounds the memory: an unbounded table "
            "is a way of letting a client choose how much memory the proxy uses."
        ),
        fr=(
            f"La table déclare la taille {taille.group(1)}, la recette demande "
            f"{recette['taille']}. La taille borne la mémoire : une table sans "
            "borne est une façon de laisser un client décider de la mémoire que "
            "le proxy consomme."
        ),
    )
    assert "type:ip" in entete.replace(" ", ""), message(
        en=(
            f"The table is not of type ip: {entete!r}. The recipe asks for the "
            "client's address to be counted, and the type is what makes that "
            "possible."
        ),
        fr=(
            f"La table n'est pas de type ip : {entete!r}. La recette demande de "
            "compter l'adresse du client, et c'est le type qui le permet."
        ),
    )

    _rafale(poste, ip_edge, 2)
    assert _entree(edge, recette, ip_poste) is not None, message(
        en="The entry is not created by traffic: nothing can be measured.",
        fr="L'entrée n'est pas créée par le trafic : il n'y a rien à mesurer.",
    )

    expiration = int(recette["expiration"])
    assert _attendre_absence(edge, recette, ip_poste, expiration + 15), message(
        en=(
            f"The entry for {ip_poste} is still in the table more than "
            f"{expiration}s after its last request. `expire` is what frees the "
            "memory: without it, or with it too long, a table bounded in size "
            "fills up and stops tracking anything new."
        ),
        fr=(
            f"L'entrée de {ip_poste} est encore dans la table plus de "
            f"{expiration} s après sa dernière requête. `expire` est ce qui libère "
            "la mémoire : sans lui, ou avec une valeur trop longue, une table "
            "bornée en taille se remplit et cesse de suivre quoi que ce soit de "
            "nouveau."
        ),
    )


def test_le_dossier_dit_ce_que_la_table_ne_protege_pas(edge, recette) -> None:
    """Relu par un humain. Le test vérifie la présence et deux sujets.

    CE QUE CE TEST NE FAIT PAS : juger le raisonnement. Les deux sujets
    exigés sont ceux qu'on ne peut pas deviner en lisant la configuration, et
    qui font la différence entre une limite qu'on a réglée et une limite dont
    on connaît la portée.
    """
    contenu = edge.run(f"cat {recette['dossier']} 2>/dev/null").stdout
    assert contenu.strip(), message(
        en=(
            f"{recette['dossier']} is missing or empty. The recipe asks for a "
            "dossier saying what this table does not protect."
        ),
        fr=(
            f"{recette['dossier']} est absent ou vide. La recette demande un "
            "dossier qui dise ce que cette table ne protège pas."
        ),
    )
    assert len(contenu) >= 400, message(
        en=f"{recette['dossier']} holds {len(contenu)} characters: two limits need more.",
        fr=f"{recette['dossier']} porte {len(contenu)} caractères : deux limites en demandent plus.",
    )

    sujets = (
        (
            "la portée d'une table, qui ne dépasse pas l'instance",
            ("instance", "peers", "processus", "process"),
        ),
        (
            "le partage d'une adresse par plusieurs clients",
            ("nat", "partag", "shared", "mobile", "proxy"),
        ),
    )
    minuscules = contenu.lower()
    for sujet, motifs in sujets:
        assert any(motif in minuscules for motif in motifs), message(
            en=(
                f"{recette['dossier']} does not cover {sujet}. These are the two "
                "limits that are not guessable from the configuration, and they "
                "are what separates a limit you tuned from a limit whose reach "
                "you know."
            ),
            fr=(
                f"{recette['dossier']} ne traite pas {sujet}. Ce sont les deux "
                "limites qu'on ne devine pas en lisant la configuration, et "
                "elles font la différence entre une limite qu'on a réglée et une "
                "limite dont on connaît la portée."
            ),
        )
