"""Verify legitimate traffic passes, abuse is refused, the grouping key cannot
be forged, and the public route does not inherit the administration penalty.

LE PIEGE CENTRAL : CE QUI SERT DE CLE

Regrouper par adresse IP est le reflexe, et il est faux ici : les
utilisateurs sont derriere un NAT, donc ils partagent une adresse, et
l'abus d'un seul les refuse tous. Mais regrouper par un en-tete que
l'appelant choisit lui-meme est pire : il suffit d'en changer a chaque
requete.

La politique du lab tranche : la cle d'API distingue les clients, et le
X-Forwarded-For n'est cru que du proxy amont declare. Le troisieme test
mesure les deux cotes de cet arbitrage.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _rafale(poste, ip: str, chemin: str, nombre: int,
            entetes: str = "", pause: str = "") -> list[str]:
    """Les codes de statut d'une rafale, dans l'ordre."""
    repos = f"sleep {pause}; " if pause else ""
    sortie = poste.run(
        f"for i in $(seq 1 {nombre}); do {repos}"
        f"curl -s -o /dev/null --max-time 10 -w '%{{http_code}}\\n' "
        f"{entetes} http://{ip}{chemin}; done"
    ).stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def _attendre_le_calme(poste, ip: str, secondes: int = 20) -> None:
    """Laisse les compteurs retomber entre deux mesures.

    Sans cela, un test herite de la rafale du precedent et echoue pour une
    raison qui n'est pas la sienne.
    """
    for _ in range(secondes):
        if _rafale(poste, ip, "/public", 1,
                   "-H 'X-Cle-Api: cle-alpha'") == ["200"]:
            return
        time.sleep(1)


def test_le_trafic_legitime_et_la_rafale_admise_passent(poste, ip_edge) -> None:
    """L'ancrage. Une limite qui refuse le trafic normal est une panne.

    La politique admet 10 requetes par seconde et une rafale de 20 : on en
    envoie 15 d'un coup, ce qui tient dans la rafale annoncee.
    """
    _attendre_le_calme(poste, ip_edge)
    codes = _rafale(poste, ip_edge, "/public", 15, "-H 'X-Cle-Api: cle-alpha'")
    refuses = [c for c in codes if c != "200"]
    assert not refuses, message(
        en=(
            f"{len(refuses)} of 15 legitimate requests were refused ({refuses}). "
            "The policy allows 10 r/s with a burst of 20: a limit that refuses "
            "normal traffic is an outage you inflict on yourself."
        ),
        fr=(
            f"{len(refuses)} requêtes légitimes sur 15 ont été refusées "
            f"({refuses}). La politique admet 10 r/s avec une rafale de 20 : "
            "une limite qui refuse le trafic normal est une panne qu'on "
            "s'inflige."
        ),
    )


def test_un_abus_recoit_le_refus_attendu(poste, ip_edge) -> None:
    """Et le refus est un 429, pas un 503.

    Le defaut de Nginx est 503, qui dit « service indisponible » : un client
    bien eleve le lit comme une panne et reessaie plus fort. 429 dit
    « trop de requetes », et c'est la seule reponse qui invite a ralentir.
    """
    _attendre_le_calme(poste, ip_edge)
    codes = _rafale(poste, ip_edge, "/public", 60, "-H 'X-Cle-Api: cle-alpha'")
    refuses = [c for c in codes if c != "200"]
    assert refuses, message(
        en=(
            "60 requests in a row were all accepted: no rate limit is in force "
            "on /public."
        ),
        fr=(
            "60 requêtes d'affilée ont toutes été acceptées : aucune limite de "
            "débit ne s'applique sur /public."
        ),
    )
    assert all(c == "429" for c in refuses), message(
        en=(
            f"The refusals are {sorted(set(refuses))}, not 429. Nginx answers "
            "503 by default, which reads as an outage and invites a retry; 429 "
            "is the only answer that asks the caller to slow down."
        ),
        fr=(
            f"Les refus sont {sorted(set(refuses))}, et non 429. Nginx répond "
            "503 par défaut, ce qui se lit comme une panne et invite à "
            "réessayer ; 429 est la seule réponse qui demande de ralentir."
        ),
    )


def test_le_regroupement_ne_croit_pas_une_adresse_forgee(poste, ip_edge) -> None:
    """CRITIQUE. Les deux cotes de l'arbitrage.

    D'abord : une adresse forgee ne doit pas faire echapper a la limite.
    Ensuite : deux cles differentes ne doivent pas se penaliser l'une
    l'autre, puisque les utilisateurs sont derriere un NAT et partagent
    l'adresse.
    """
    _attendre_le_calme(poste, ip_edge)
    codes = poste.run(
        "for i in $(seq 1 60); do "
        f"curl -s -o /dev/null --max-time 10 -w '%{{http_code}}\\n' "
        f"-H 'X-Cle-Api: cle-alpha' "
        f"-H \"X-Forwarded-For: 203.0.113.$i\" http://{ip_edge}/public; done"
    ).stdout
    refuses = [c.strip() for c in codes.splitlines() if c.strip() not in ("200", "")]
    assert refuses, message(
        en=(
            "Changing the X-Forwarded-For on every request was enough to escape "
            "the limit entirely. Nginx is believing an address the caller chose: "
            "`set_real_ip_from` must list the trusted upstream proxy only, and "
            "the grouping key must not be something the caller controls."
        ),
        fr=(
            "Changer le X-Forwarded-For à chaque requête a suffi à échapper "
            "complètement à la limite. Nginx croit une adresse que l'appelant "
            "choisit : `set_real_ip_from` ne doit lister que le proxy amont de "
            "confiance, et la clé de regroupement ne doit pas être quelque "
            "chose que l'appelant contrôle."
        ),
    )

    # L'autre cote : une cle differente ne doit pas heriter de la penalite.
    autre = _rafale(poste, ip_edge, "/public", 5, "-H 'X-Cle-Api: cle-beta'")
    assert autre.count("200") >= 4, message(
        en=(
            f"A different API key was refused right away ({autre}), although it "
            "sent nothing. Users behind a NAT share one address: grouping by "
            "address penalises them all for one caller's abuse."
        ),
        fr=(
            f"Une autre clé d'API a été refusée d'emblée ({autre}), alors "
            "qu'elle n'avait rien envoyé. Des utilisateurs derrière un NAT "
            "partagent une adresse : regrouper par adresse les pénalise tous "
            "pour l'abus d'un seul."
        ),
    )


def test_la_route_publique_ne_partage_pas_la_penalite_de_l_administration(
    poste, ip_edge
) -> None:
    """Deux routes, deux compteurs : marteler l'une ne ferme pas l'autre."""
    _attendre_le_calme(poste, ip_edge)
    administration = _rafale(
        poste, ip_edge, "/admin", 40, "-H 'X-Cle-Api: cle-alpha'"
    )
    assert "429" in administration, message(
        en=(
            "40 requests on /admin were all accepted: the stricter limit the "
            "policy asks for on the administration route is not in force."
        ),
        fr=(
            "40 requêtes sur /admin ont toutes été acceptées : la limite plus "
            "stricte que la politique demande sur la route d'administration ne "
            "s'applique pas."
        ),
    )

    public = _rafale(poste, ip_edge, "/public", 5, "-H 'X-Cle-Api: cle-alpha'")
    assert public.count("200") >= 4, message(
        en=(
            f"Right after hammering /admin, /public answers {public}. The two "
            "routes share one counter: give each its own zone, so the "
            "administration penalty does not close the public route."
        ),
        fr=(
            f"Juste après avoir martelé /admin, /public répond {public}. Les "
            "deux routes partagent un compteur : donnez à chacune sa zone, pour "
            "que la pénalité de l'administration ne ferme pas la route "
            "publique."
        ),
    )
