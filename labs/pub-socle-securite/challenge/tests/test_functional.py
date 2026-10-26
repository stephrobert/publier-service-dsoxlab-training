"""Verify the access policy allows what it must, refuses what it must, resists
bypass attempts, and keeps secrets out of the logs.

LES QUATRE CONTROLES, ET POURQUOI TROIS SONT CRITIQUES

Le setup pose trois routes publiées et une politique VIDE : tout passe, tout
en-tête d'identité est cru, et le journal conserve tout. Aucun test n'est
donc vert sans travail.

CE QUI EST MESURE, ET CE QUI NE L'EST JAMAIS

Jamais la présence d'une directive. Une politique se juge sur ce que le
service répond, pas sur ce qu'elle déclare : un fichier peut nommer une
règle que le garde n'applique pas, parce qu'elle vise un préfixe qui ne
correspond à rien. On envoie donc de vraies requêtes, depuis le client
indépendant, et on lit le STATUT **et** le CORPS.

Lire le corps n'est pas du luxe : un 200 qui renvoie la page publique sur
`/admin` n'est pas une fuite, un 200 qui renvoie « revocation des acces » en
est une. Le statut seul ne les distingue pas.
"""

from __future__ import annotations

import secrets

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
WORK = "/opt/pub-socle-securite"

UTILISATEUR = "jeton-utilisateur-7f3a"
ADMIN = "jeton-admin-91c4"

# Les marques que l'application met dans chaque réponse. Elles disent QUEL
# contenu est sorti, là où un code de statut ne dit que s'il est sorti.
MARQUE_PUBLIC = "PUBLIC :"
MARQUE_COMPTE = "COMPTE :"
MARQUE_ADMIN = "ADMINISTRATION :"


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _appel(poste, ip: str, chemin: str, jeton: str = "",
           entetes: str = "", port: int = 80) -> tuple[str, str]:
    """Une requête depuis le client indépendant, rendue en (statut, corps).

    Le corps et le statut voyagent ensemble, séparés par un marqueur : un
    second appel pour obtenir le statut mesurerait une autre requête, et donc
    potentiellement un autre état.
    """
    auth = f"-H 'Authorization: Bearer {jeton}'" if jeton else ""
    res = poste.run(
        f"curl -s --max-time 10 -w '\\n@@STATUT@@%{{http_code}}' "
        f"{auth} {entetes} http://{ip}:{port}{chemin}"
    )
    sortie = res.stdout.rsplit("@@STATUT@@", 1)
    corps = sortie[0] if len(sortie) == 2 else res.stdout
    statut = sortie[1].strip() if len(sortie) == 2 else "000"
    return statut, corps


def test_le_trafic_legitime_reste_fonctionnel(poste, ip_edge) -> None:
    """Les trois catégories autorisées passent, ET une politique existe.

    Ce test est l'ancrage de tous les autres : une politique qui refuse
    tout satisferait les refus sans rien protéger, puisqu'il n'y aurait
    plus de service à protéger.

    MAIS IL EXIGE AUSSI QUE LA POLITIQUE SOIT LÀ

    Sans cette seconde moitié, il passait sur l'état de départ : avant
    toute politique, le trafic légitime fonctionne évidemment, et le lab
    donnait 25 points sur 100 à qui n'avait rien fait. Mesuré le
    2026-10-26.

    « Le service marche » n'est une propriété intéressante que mis en
    regard de « et il est protégé ». Prises séparément, les deux moitiés
    sont triviales : ne rien configurer satisfait la première, tout
    refuser satisfait la seconde.
    """
    cas = [
        ("public anonyme", "/", "", MARQUE_PUBLIC),
        ("compte avec le jeton utilisateur", "/compte", UTILISATEUR, MARQUE_COMPTE),
        ("administration avec le jeton admin", "/admin", ADMIN, MARQUE_ADMIN),
    ]
    echecs = []
    for libelle, chemin, jeton, marque in cas:
        statut, corps = _appel(poste, ip_edge, chemin, jeton)
        if statut != "200" or marque not in corps:
            echecs.append(f"{libelle} : HTTP {statut}, corps {corps.strip()[:60]!r}")
    assert not echecs, message(
        en=(
            "Legitimate traffic must keep working. Refusing everyone is not a "
            "policy, it is an outage. " + " ; ".join(echecs)
        ),
        fr=(
            "Le trafic légitime doit continuer de fonctionner. Refuser tout le "
            "monde n'est pas une politique, c'est une panne. " + " ; ".join(echecs)
        ),
    )

    # Et la politique EXISTE : sans jeton, l'administration est refusée.
    # C'est le plus petit refus qui distingue un service protégé d'un
    # service nu, et c'est ce qui fait que ce test ne passe pas sur l'état
    # de départ.
    statut, corps = _appel(poste, ip_edge, "/admin", "")
    assert statut != "200", message(
        en=(
            f"/admin answered {statut} with no token at all "
            f"({corps.strip()[:80]!r}). Legitimate traffic working proves "
            "nothing on its own: before any policy, everything works. The "
            "property is the conjunction, not either half."
        ),
        fr=(
            f"/admin a répondu {statut} sans aucun jeton "
            f"({corps.strip()[:80]!r}). Que le trafic légitime fonctionne ne "
            "prouve rien en soi : avant toute politique, tout fonctionne. La "
            "propriété est la conjonction, pas l'une des deux moitiés."
        ),
    )


def test_les_routes_sensibles_refusent_qui_n_y_a_pas_droit(poste, ip_edge) -> None:
    """CRITIQUE. La matrice complète des refus, statut et corps.

    On vérifie aussi que le contenu protégé n'apparaît NULLE PART dans la
    réponse : un service qui refuse en 403 mais joint la page en corps a
    refusé pour la forme.
    """
    cas = [
        ("compte, anonyme", "/compte", "", MARQUE_COMPTE),
        ("administration, anonyme", "/admin", "", MARQUE_ADMIN),
        ("administration, jeton utilisateur", "/admin", UTILISATEUR, MARQUE_ADMIN),
    ]
    echecs = []
    for libelle, chemin, jeton, interdit in cas:
        statut, corps = _appel(poste, ip_edge, chemin, jeton)
        if statut not in {"401", "403"}:
            echecs.append(f"{libelle} : HTTP {statut} au lieu d'un refus")
        elif interdit in corps:
            echecs.append(
                f"{libelle} : refusé en {statut}, mais le corps contient "
                f"quand même le contenu protégé"
            )
    assert not echecs, message(
        en=(
            "Sensitive routes must refuse callers without the right identity, "
            "and must not leak the protected content in the body of the "
            "refusal. " + " ; ".join(echecs)
        ),
        fr=(
            "Les routes sensibles doivent refuser l'appelant qui n'a pas "
            "l'identité requise, et ne pas laisser le contenu protégé dans le "
            "corps du refus. " + " ; ".join(echecs)
        ),
    )


def test_ni_l_origine_directe_ni_un_entete_forge_ne_contournent(
    poste, ip_edge
) -> None:
    """CRITIQUE. Les deux contournements, mesurés depuis le réseau client.

    Une politique posée devant une porte que l'on peut contourner ne protège
    rien. Les deux chemins de contournement sont ici l'accès direct à
    l'application, et l'en-tête d'identité forgé par l'appelant lui-même.
    """
    statut, corps = _appel(poste, ip_edge, "/admin", port=18090)
    assert statut != "200" or MARQUE_ADMIN not in corps, message(
        en=(
            "The application answers directly on port 18090 from the client "
            "network, so the whole policy can be walked around. Close that "
            "door: bind the application to the loopback interface, or refuse "
            "the port from outside."
        ),
        fr=(
            "L'application répond directement sur le port 18090 depuis le "
            "réseau client : toute la politique se contourne. Fermez cette "
            "porte, en liant l'application à la boucle locale ou en refusant "
            "le port depuis l'extérieur."
        ),
    )

    statut, corps = _appel(
        poste, ip_edge, "/admin", entetes="-H 'X-Identite: admin'"
    )
    assert statut in {"401", "403"} and MARQUE_ADMIN not in corps, message(
        en=(
            "A forged `X-Identite: admin` header, sent by an untrusted caller, "
            f"was believed (HTTP {statut}). An identity header is only "
            "trustworthy from an address you listed in `proxys_de_confiance`."
        ),
        fr=(
            "Un en-tête `X-Identite: admin` forgé par un appelant non fiable a "
            f"été cru (HTTP {statut}). Un en-tête d'identité ne vaut que "
            "depuis une adresse inscrite dans `proxys_de_confiance`."
        ),
    )


def test_aucun_secret_seme_ne_survit_dans_les_sorties(poste, edge, ip_edge) -> None:
    """CRITIQUE. Une valeur sentinelle, semée puis cherchée dans les sorties.

    La sentinelle est tirée au hasard à chaque passage : une valeur figée
    pourrait rester d'un essai précédent et faire échouer le test sur le
    travail d'hier, ou pire, le faire passer parce qu'elle a été effacée une
    fois.

    On cherche dans le journal ET dans le dossier : un secret recopié dans un
    résumé reste un secret en clair sur le disque.
    """
    sentinelle = f"sentinelle-{secrets.token_hex(8)}"
    _appel(
        poste, ip_edge, "/", jeton=sentinelle,
        entetes=f"-H 'Cookie: session={sentinelle}'",
    )

    fuites = []
    for fichier in (f"{WORK}/acces.log", f"{WORK}/dossier.json"):
        trouve = edge.run(f"sudo grep -c {sentinelle} {fichier}")
        compte = trouve.stdout.strip()
        if compte.isdigit() and int(compte) > 0:
            fuites.append(f"{fichier} ({compte} occurrence(s))")

    assert not fuites, message(
        en=(
            f"The sentinel value sent in Cookie and Authorization was written "
            f"in clear to {', '.join(fuites)}. Credentials kept in a log stay "
            "readable for as long as the log lives: list those headers under "
            "`journal.effacer`."
        ),
        fr=(
            f"La valeur sentinelle envoyée dans Cookie et Authorization a été "
            f"écrite en clair dans {', '.join(fuites)}. Des identifiants "
            "conservés dans un journal restent lisibles aussi longtemps que le "
            "journal vit : déclarez ces en-têtes sous `journal.effacer`."
        ),
    )

    # L'autre moitié : effacer ne doit pas vider le journal. Un journal muet
    # protege parfaitement les secrets et n'aide plus personne.
    lignes = edge.run(f"sudo wc -l {WORK}/acces.log").stdout.strip().split(" ")[0]
    assert lignes.isdigit() and int(lignes) > 0, message(
        en=(
            "The access log is empty. Redacting is not the same as logging "
            "nothing: a silent log protects every secret and helps nobody."
        ),
        fr=(
            "Le journal d'accès est vide. Effacer n'est pas ne rien "
            "journaliser : un journal muet protège tous les secrets et n'aide "
            "plus personne."
        ),
    )
