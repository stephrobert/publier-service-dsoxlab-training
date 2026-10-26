"""Verify security headers, admin authentication, rate limiting, and method
policy on an HAProxy frontend.

CE QUE CHAQUE TEST DOIT POUVOIR DIRE

« Serait-il vert si l'apprenant ne faisait rien ? » Le setup pose HAProxy
publiant l'application sans aucune des quatre protections : pas d'en-tête,
`/admin` ouvert, aucune limite de débit, méthodes d'écriture transmises.

LA PRÉCAUTION QUI TRAVERSE CE FICHIER

Un refus se prouve en montrant ce qui passe ENCORE. Une configuration qui
rejette tout satisferait « /admin répond 401 », « le débit excessif est
refusé » et « DELETE est refusée » d'un seul coup, en ayant simplement cassé
le service. Chaque test porte donc son contre-exemple : la requête qui doit
continuer d'aboutir, et la preuve qu'elle a bien atteint le BACKEND, que son
corps nomme.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
URL = "http://app.lab.test"
RESOLUTION = "--resolve app.lab.test:80:127.0.0.1"
IDENTIFIANTS = "labadmin:Lab-Admin-Only"
# Le backend nomme le chemin et la méthode : une réponse qui porte cette
# marque vient de lui, et non d'une page d'erreur de HAProxy.
MARQUE = "HAProxy protection backend:"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _code(edge, chemin: str = "/health", methode: str = "GET",
          options: str = "") -> str:
    res = edge.run(
        f"curl --max-time 5 --silent --show-error --request {methode} "
        f"--output /dev/null --write-out '%{{http_code}}' "
        f"{options} {RESOLUTION} {URL}{chemin}"
    )
    return res.stdout.strip()


def _corps(edge, chemin: str = "/health", options: str = "") -> str:
    res = edge.run(
        f"curl --max-time 5 --silent --show-error {options} "
        f"{RESOLUTION} {URL}{chemin}"
    )
    return res.stdout


def _attendre_le_retour_a_la_normale(edge, secondes: int = 30) -> str:
    """Attend que le débit redevienne acceptable, et rend le dernier code.

    Les tests partagent une adresse source : sans cette attente, le test du
    débit laisserait le compteur chaud et ferait échouer le suivant pour une
    raison qui n'a rien à voir avec lui.
    """
    dernier = ""
    for _ in range(secondes):
        dernier = _code(edge)
        if dernier == "200":
            return dernier
        time.sleep(1)
    return dernier


def test_entetes_de_securite_sont_presentes(edge) -> None:
    """Les quatre en-têtes sont là, SUR une réponse qui vient du backend.

    Les chercher sur n'importe quelle réponse ne suffirait pas : HAProxy
    peut les poser sur ses propres pages d'erreur, et le lab serait vert sur
    un service cassé.
    """
    res = edge.run(
        f"curl --max-time 5 --silent --show-error --dump-header - "
        f"{RESOLUTION} {URL}/health"
    )
    assert res.rc == 0 and MARQUE in res.stdout, message(
        en=(
            "The normal request no longer reaches the backend. Headers are "
            "pointless on a service that stopped working: fix the frontend "
            f"first (answer: {res.stdout.strip()[:160]!r})."
        ),
        fr=(
            "La requête normale n'atteint plus le backend. Des en-têtes sur un "
            "service qui ne répond plus ne servent à rien : réparez d'abord le "
            f"frontend (réponse : {res.stdout.strip()[:160]!r})."
        ),
    )
    attendues = (
        "X-Content-Type-Options: nosniff",
        "X-Frame-Options: DENY",
        "Referrer-Policy: no-referrer",
        "Content-Security-Policy: default-src 'self'; frame-ancestors 'none'",
    )
    bas = res.stdout.lower()
    manquantes = [en_tete for en_tete in attendues if en_tete.lower() not in bas]
    assert not manquantes, message(
        en=f"Required security headers are missing: {manquantes}.",
        fr=f"En-têtes de sécurité manquants : {manquantes}.",
    )


def test_admin_exige_les_identifiants_fournis(edge) -> None:
    """Anonyme refusé, authentifié servi PAR LE BACKEND.

    Le second volet est ce qui distingue une authentification d'un simple
    blocage : refuser tout le monde rendrait aussi 401 à l'anonyme.
    """
    anonyme = _code(edge, "/admin")
    assert anonyme == "401", message(
        en=(
            f"/admin answers {anonyme!r} to an anonymous caller; it must "
            "challenge with 401. A 403 blocks without offering a way in, and "
            "a 200 does not protect anything."
        ),
        fr=(
            f"/admin répond {anonyme!r} à un appelant anonyme ; il doit "
            "réclamer des identifiants avec un 401. Un 403 bloque sans offrir "
            "d'entrée, et un 200 ne protège rien."
        ),
    )
    authentifie = _corps(edge, "/admin", options=f"--user {IDENTIFIANTS}")
    assert MARQUE in authentifie, message(
        en=(
            "With the supplied credentials, /admin must serve the backend. "
            "Refusing everyone is not authentication, it is removal "
            f"(answer: {authentifie.strip()[:160]!r})."
        ),
        fr=(
            "Avec les identifiants fournis, /admin doit servir le backend. "
            "Refuser tout le monde n'est pas authentifier, c'est supprimer "
            f"(réponse : {authentifie.strip()[:160]!r})."
        ),
    )


def test_le_debit_abusif_est_refuse_et_le_debit_normal_passe(edge) -> None:
    """Une rafale est écrêtée, et le service revient de lui-même.

    TROIS CHOSES SE PROUVENT ICI, et aucune ne suffit seule :

    1. la rafale rencontre des 429, donc une limite existe ;
    2. la rafale contient AUSSI des 200, donc c'est une limite et non un mur
       qui refuse par principe ;
    3. le service redevient disponible une fois la fenêtre écoulée, donc la
       limite libère, au lieu de bannir définitivement.
    """
    rafale = edge.run(
        "for i in $(seq 1 40); do "
        f"curl --max-time 5 --silent --output /dev/null "
        f"--write-out '%{{http_code}}\\n' {RESOLUTION} {URL}/health; "
        "done"
    )
    codes = [ligne.strip() for ligne in rafale.stdout.splitlines() if ligne.strip()]
    assert len(codes) >= 30, message(
        en=(
            f"The burst produced only {len(codes)} answers out of 40: the "
            "service is not answering well enough for the measurement to mean "
            "anything."
        ),
        fr=(
            f"La rafale n'a produit que {len(codes)} réponses sur 40 : le "
            "service ne répond pas assez pour que la mesure veuille dire "
            "quelque chose."
        ),
    )
    refuses = codes.count("429")
    servis = codes.count("200")
    assert refuses > 0, message(
        en=(
            f"40 requests in a row from one source were all accepted "
            f"({servis} answered 200, none 429). Add a stick-table counting "
            "the HTTP request rate per source, and deny with 429 above the "
            "documented threshold."
        ),
        fr=(
            f"40 requêtes d'affilée depuis une même source ont toutes été "
            f"acceptées ({servis} en 200, aucune en 429). Ajoutez une "
            "stick-table qui compte le débit de requêtes par source, et "
            "refusez en 429 au-delà du seuil annoncé."
        ),
    )
    assert servis > 0, message(
        en=(
            f"The whole burst was refused ({refuses} answers in 429, none in "
            "200). That is not a rate limit, it is a closed door: the first "
            "requests, below the threshold, must go through."
        ),
        fr=(
            f"Toute la rafale a été refusée ({refuses} réponses en 429, "
            "aucune en 200). Ce n'est pas une limite de débit mais une porte "
            "fermée : les premières requêtes, sous le seuil, doivent passer."
        ),
    )

    retour = _attendre_le_retour_a_la_normale(edge)
    assert retour == "200", message(
        en=(
            f"30 s after the burst, a single request still answers {retour!r}. "
            "A rate limit releases once its window has passed; this one bans "
            "for good."
        ),
        fr=(
            f"30 s après la rafale, une requête isolée répond encore "
            f"{retour!r}. Une limite de débit relâche une fois sa fenêtre "
            "écoulée ; celle-ci bannit définitivement."
        ),
    )


def test_les_methodes_d_ecriture_sont_refusees(edge) -> None:
    """DELETE et PUT refusées, GET toujours servi par le backend."""
    _attendre_le_retour_a_la_normale(edge)
    refuses = {}
    for methode in ("DELETE", "PUT"):
        code = _code(edge, methode=methode)
        if code not in {"403", "405"}:
            refuses[methode] = code
    assert not refuses, message(
        en=(
            f"These write methods still reach the application: {refuses}. "
            "The application does not use them; refuse them at the frontend "
            "with 403 or 405."
        ),
        fr=(
            f"Ces méthodes d'écriture atteignent encore l'application : "
            f"{refuses}. L'application ne s'en sert pas ; refusez-les au "
            "frontend, en 403 ou 405."
        ),
    )
    lecture = _corps(edge)
    assert MARQUE in lecture, message(
        en=(
            "GET no longer reaches the backend. Restricting the methods must "
            "not take the ones the application needs with it "
            f"(answer: {lecture.strip()[:160]!r})."
        ),
        fr=(
            "GET n'atteint plus le backend. Restreindre les méthodes ne doit "
            "pas emporter celles dont l'application a besoin "
            f"(réponse : {lecture.strip()[:160]!r})."
        ),
    )
