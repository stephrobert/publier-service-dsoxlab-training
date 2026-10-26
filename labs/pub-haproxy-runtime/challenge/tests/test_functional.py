"""Verify that reading and acting are separated by identity, that taking a
server out really changes the assignment, that the decision survives a
reload, and that the documented return to nominal actually runs.

CE QUE LE SETUP POSE : un socket unique en mode 666 et `level admin`, aucun
fichier d'etat, et trois identites de test sans sudo.

POURQUOI LE TEST N'EXECUTE AUCUNE OPERATION DESTRUCTRICE

Prouver qu'une identite a le droit d'administrer ne demande pas de s'en
servir pour abimer quelque chose. Retirer un serveur du service puis l'y
remettre suffit, et c'est reversible. Un test qui viderait une table ou
tuerait des sessions pour demontrer un droit laisserait la machine dans un
etat que le test suivant mesurerait.

POURQUOI L'ETAT RAPPORTE NE SUFFIT PAS

`show stat` dit ce que HAProxy PENSE. Le trafic dit ce qu'il FAIT. Les deux
peuvent differer, et c'est precisement le cas d'une decision ecrite dans un
fichier marqueur que personne ne lit : l'etat affiche change, l'affectation
non.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-runtime/recette.txt"
MARQUE = "pub-haproxy-runtime service"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


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
        "socket_lecture",
        "groupe_lecture",
        "identite_lecture",
        "socket_admin",
        "groupe_admin",
        "identite_admin",
        "identite_interdite",
        "backend",
        "serveur_a",
        "serveur_b",
        "retour_nominal",
        "dossier",
    )
    return {cle: _valeur(edge, cle) for cle in cles}


def _comme(edge, identite: str, socket: str, commande: str):
    """Joue une commande de pilotage SOUS une identite donnee."""
    return edge.run(
        f"sudo -u {identite} sh -c "
        f"\"echo '{commande}' | socat -t3 stdio {socket} 2>&1\""
    )


def _repond(sortie: str) -> bool:
    """Vrai si le socket a rendu quelque chose d'exploitable."""
    return "Nbthread" in sortie or "# pxname" in sortie or "Name:" in sortie


def _etat(edge, recette, serveur: str) -> str:
    brut = edge.run(
        f"echo 'show stat' | sudo socat -t3 stdio {recette['socket_admin']}"
    ).stdout
    lignes = [ligne for ligne in brut.splitlines() if ligne.strip()]
    if not lignes or not lignes[0].startswith("#"):
        return ""
    colonnes = lignes[0].lstrip("# ").rstrip(",").split(",")
    for ligne in lignes[1:]:
        champs = dict(zip(colonnes, ligne.split(","), strict=False))
        if champs.get("pxname") == recette["backend"] and champs.get("svname") == serveur:
            return champs.get("status", "")
    return ""


def _qui_repond(poste, ip: str, nombre: int = 12) -> set[str]:
    vus = set()
    for _ in range(nombre):
        corps = poste.run(f"curl -s --max-time 10 http://{ip}/").stdout
        for ligne in corps.splitlines():
            if ligne.startswith(MARQUE):
                vus.add(ligne.rsplit(" ", 1)[-1])
    return vus


def test_seule_l_identite_prevue_peut_administrer(edge, recette) -> None:
    """CRITIQUE : les trois identités, et aucune opération destructrice."""
    lecture = _comme(
        edge, recette["identite_lecture"], recette["socket_lecture"], "show info"
    )
    assert _repond(lecture.stdout), message(
        en=(
            f"{recette['identite_lecture']} cannot read the state through "
            f"{recette['socket_lecture']} ({lecture.stdout.strip()[:160]!r}). "
            "Separating reading from acting means giving reading its own way "
            "in, not removing it."
        ),
        fr=(
            f"{recette['identite_lecture']} ne peut pas lire l'état par "
            f"{recette['socket_lecture']} ({lecture.stdout.strip()[:160]!r}). "
            "Séparer la lecture de l'action consiste à donner sa propre voie à "
            "la lecture, pas à la supprimer."
        ),
    )

    tentative = _comme(
        edge,
        recette["identite_lecture"],
        recette["socket_lecture"],
        f"set server {recette['backend']}/{recette['serveur_b']} state drain",
    )
    etat = _etat(edge, recette, recette["serveur_b"])
    assert "DRAIN" not in etat, message(
        en=(
            f"{recette['identite_lecture']} took a server out of service "
            f"through the read socket (state: {etat!r}, answer: "
            f"{tentative.stdout.strip()[:160]!r}). A metrics collector, a probe "
            "or a monitoring script needs to read; giving them the right to act "
            "is giving away the proxy to whatever runs them."
        ),
        fr=(
            f"{recette['identite_lecture']} a sorti un serveur du service par le "
            f"socket de lecture (état : {etat!r}, réponse : "
            f"{tentative.stdout.strip()[:160]!r}). Un collecteur de métriques, "
            "une sonde ou un script de supervision a besoin de lire ; leur "
            "donner le droit d'agir revient à confier le proxy à ce qui les "
            "exécute."
        ),
    )

    for socket in (recette["socket_lecture"], recette["socket_admin"]):
        refuse = _comme(edge, recette["identite_interdite"], socket, "show info")
        assert not _repond(refuse.stdout), message(
            en=(
                f"{recette['identite_interdite']}, which belongs to neither "
                f"group, reads {socket}. A socket in mode 666 is an "
                "administration interface open to every account on the machine, "
                "and nothing announces it."
            ),
            fr=(
                f"{recette['identite_interdite']}, qui n'appartient à aucun des "
                f"deux groupes, lit {socket}. Un socket en mode 666 est une "
                "interface d'administration ouverte à tous les comptes de la "
                "machine, et rien ne le signale."
            ),
        )

    agit = _comme(
        edge,
        recette["identite_admin"],
        recette["socket_admin"],
        f"set server {recette['backend']}/{recette['serveur_b']} state drain",
    )
    etat = _etat(edge, recette, recette["serveur_b"])
    try:
        assert "DRAIN" in etat, message(
            en=(
                f"{recette['identite_admin']} could not take a server out of "
                f"service (state: {etat!r}, answer: {agit.stdout.strip()[:160]!r}). "
                "Restricting rights is not removing them: the operator must still "
                "be able to work."
            ),
            fr=(
                f"{recette['identite_admin']} n'a pas pu sortir un serveur du "
                f"service (état : {etat!r}, réponse : {agit.stdout.strip()[:160]!r}). "
                "Restreindre les droits n'est pas les supprimer : l'exploitant "
                "doit encore pouvoir travailler."
            ),
        )
    finally:
        _comme(
            edge,
            recette["identite_admin"],
            recette["socket_admin"],
            f"set server {recette['backend']}/{recette['serveur_b']} state ready",
        )


def test_le_retrait_change_reellement_l_affectation(
    edge, poste, recette, ip_edge
) -> None:
    """L'état rapporté ne suffit pas : c'est le trafic qui décide.

    ET LE RETRAIT DOIT VENIR DE LA BONNE IDENTITÉ

    Sans cette seconde exigence, ce test passait sur l'état de départ :
    le socket y est ouvert en mode 666, donc la commande de drainage
    fonctionne déjà, et le lab donnait 25/100 à qui n'avait rien fait.
    Mesuré le 2026-10-26.

    Un drainage qui marche n'est pas une capacité d'exploitation : c'en est
    une si, et seulement si, elle est réservée à qui doit l'avoir.
    """
    avant = _qui_repond(poste, ip_edge)
    assert {recette["serveur_a"], recette["serveur_b"]} <= avant, message(
        en=f"Both servers must answer before the measurement: seen {sorted(avant)}.",
        fr=f"Les deux serveurs doivent répondre avant la mesure : vus {sorted(avant)}.",
    )

    # L'identité interdite ne doit RIEN pouvoir retirer. On le vérifie avant
    # de mesurer le retrait lui-même : un drainage qui marche pour tout le
    # monde n'est pas le drainage que la recette demande.
    refuse = _comme(
        edge,
        recette["identite_interdite"],
        recette["socket_admin"],
        f"set server {recette['backend']}/{recette['serveur_b']} state drain",
    )
    etat = _etat(edge, recette, recette["serveur_b"])
    assert "DRAIN" not in etat, message(
        en=(
            f"{recette['identite_interdite']}, which belongs to no group, took "
            f"a server out of service (state: {etat!r}, answer: "
            f"{refuse.stdout.strip()[:120]!r}). Draining is only an operations "
            "capability if it is reserved to whoever must have it; open to "
            "everyone, it is a way for any account on the machine to take the "
            "service down."
        ),
        fr=(
            f"{recette['identite_interdite']}, qui n'appartient à aucun groupe, "
            f"a sorti un serveur du service (état : {etat!r}, réponse : "
            f"{refuse.stdout.strip()[:120]!r}). Le drainage n'est une capacité "
            "d'exploitation que s'il est réservé à qui doit l'avoir ; ouvert à "
            "tous, c'est un moyen pour n'importe quel compte de la machine de "
            "couper le service."
        ),
    )

    _comme(
        edge,
        recette["identite_admin"],
        recette["socket_admin"],
        f"set server {recette['backend']}/{recette['serveur_b']} state drain",
    )
    try:
        time.sleep(2)
        pendant = _qui_repond(poste, ip_edge, 20)
        assert recette["serveur_b"] not in pendant, message(
            en=(
                f"{recette['serveur_b']} is reported out of service and keeps "
                f"answering ({sorted(pendant)}). `show stat` says what HAProxy "
                "thinks; traffic says what it does, and a decision that does not "
                "change the assignment is a state, not a decision."
            ),
            fr=(
                f"{recette['serveur_b']} est rapporté hors service et continue de "
                f"répondre ({sorted(pendant)}). `show stat` dit ce que HAProxy "
                "pense ; le trafic dit ce qu'il fait, et une décision qui ne "
                "change pas l'affectation est un état, pas une décision."
            ),
        )
        assert recette["serveur_a"] in pendant, message(
            en=f"Nothing answers any more once one server is out: {sorted(pendant)}.",
            fr=f"Plus rien ne répond dès qu'un serveur sort : {sorted(pendant)}.",
        )
    finally:
        _comme(
            edge,
            recette["identite_admin"],
            recette["socket_admin"],
            f"set server {recette['backend']}/{recette['serveur_b']} state ready",
        )
        time.sleep(2)


def test_la_decision_survit_a_un_rechargement(edge, poste, recette, ip_edge) -> None:
    """HAProxy doit s'en souvenir, parce que c'est lui qui affecte."""
    # L'ETAT DE DEPART DOIT ETRE EN SERVICE.
    #
    # Sans ce controle, le test peut reussir SANS RIEN PROUVER : il suffit
    # qu'un fichier d'etat laisse par un passage precedent porte deja ce
    # serveur en DRAIN, et qu'il soit charge au demarrage. On retire alors un
    # serveur deja retire, le rechargement le retrouve retire, et le test
    # conclut au vert sur une decision qu'il n'a pas vue prendre. Signale le
    # 2026-10-26 par un audit independant, et c'est le meme defaut que celui
    # qu'on corrige partout ailleurs : un controle qui conclut sans avoir
    # regarde.
    depart = _etat(edge, recette, recette["serveur_b"])
    assert "DRAIN" not in depart and "MAINT" not in depart, message(
        en=(
            f"Before anything is done, {recette['serveur_b']} is already "
            f"{depart!r}. A state file from an earlier run is being loaded, so "
            "this test would pass without ever measuring a decision. Run "
            "`dsoxlab clean` then `dsoxlab run` to start from a known state."
        ),
        fr=(
            f"Avant tout geste, {recette['serveur_b']} est déjà {depart!r}. Un "
            "fichier d'état laissé par un passage précédent est donc chargé, et "
            "ce test réussirait sans jamais mesurer de décision. Repartez d'un "
            "état connu avec `dsoxlab clean` puis `dsoxlab run`."
        ),
    )
    _comme(
        edge,
        recette["identite_admin"],
        recette["socket_admin"],
        f"set server {recette['backend']}/{recette['serveur_b']} state drain",
    )
    time.sleep(2)
    assert "DRAIN" in _etat(edge, recette, recette["serveur_b"]), message(
        en="The server was not taken out: nothing can be measured.",
        fr="Le serveur n'a pas été retiré : il n'y a rien à mesurer.",
    )

    rechargement = edge.run("sudo systemctl reload haproxy")
    assert rechargement.rc == 0, message(
        en=f"`systemctl reload haproxy` failed: {rechargement.stdout.strip()[:200]!r}",
        fr=f"`systemctl reload haproxy` a échoué : {rechargement.stdout.strip()[:200]!r}",
    )
    time.sleep(4)

    etat = _etat(edge, recette, recette["serveur_b"])
    apres = _qui_repond(poste, ip_edge, 20)
    assert "DRAIN" in etat or "MAINT" in etat, message(
        en=(
            f"After the reload, {recette['serveur_b']} is back to {etat!r}. A "
            "reload rereads the configuration and starts from it: without a "
            "state file, every runtime decision is forgotten. The reload that "
            "erases it is rarely the one you triggered on purpose, it is the one "
            "a certificate renewal fired at four in the morning."
        ),
        fr=(
            f"Après le rechargement, {recette['serveur_b']} est revenu à {etat!r}. "
            "Un rechargement relit la configuration et repart d'elle : sans "
            "fichier d'état, toute décision prise à chaud est oubliée. Le "
            "rechargement qui l'efface est rarement celui qu'on a déclenché "
            "exprès, c'est celui qu'un renouvellement de certificat a lancé à "
            "quatre heures du matin."
        ),
    )
    assert recette["serveur_b"] not in apres, message(
        en=(
            f"After the reload the state says out of service but the traffic goes "
            f"there anyway ({sorted(apres)}). The state file must be loaded at "
            "startup, not merely written."
        ),
        fr=(
            f"Après le rechargement, l'état dit hors service mais le trafic y va "
            f"quand même ({sorted(apres)}). Le fichier d'état doit être chargé au "
            "démarrage, pas seulement écrit."
        ),
    )


def test_le_retour_au_nominal_est_documente_et_execute(
    edge, poste, recette, ip_edge
) -> None:
    """La méthode de retour est JOUÉE, et le dossier relu par un humain.

    Ce test vient après celui du rechargement, et ce n'est pas un hasard : il
    laisse la machine dans l'état nominal, ce qu'un exploitant doit faire en
    partant. Un serveur laissé hors service est une panne qui ne se signale
    pas.
    """
    retour = edge.run(f"sudo {recette['retour_nominal']} 2>&1")
    assert retour.rc == 0, message(
        en=(
            f"{recette['retour_nominal']} failed (code {retour.rc}): "
            f"{retour.stdout.strip()[-300:]!r}. A return method that has never "
            "been played is not a return method."
        ),
        fr=(
            f"{recette['retour_nominal']} a échoué (code {retour.rc}) : "
            f"{retour.stdout.strip()[-300:]!r}. Une méthode de retour qui n'a "
            "jamais été jouée n'est pas une méthode de retour."
        ),
    )

    time.sleep(3)
    vus = _qui_repond(poste, ip_edge, 20)
    assert {recette["serveur_a"], recette["serveur_b"]} <= vus, message(
        en=(
            f"After the return to nominal, only {sorted(vus)} answer. Both "
            "servers must be back in service."
        ),
        fr=(
            f"Après le retour au nominal, seuls {sorted(vus)} répondent. Les deux "
            "serveurs doivent être revenus en service."
        ),
    )

    # ET IL TIENT AU RECHARGEMENT SUIVANT. Sans cette moitie, un retour qui
    # se contente de parler au socket laisserait le fichier d'etat sur
    # l'ancienne decision, et le prochain reload la ressortirait.
    edge.run("sudo systemctl reload haproxy")
    time.sleep(4)
    vus = _qui_repond(poste, ip_edge, 20)
    assert {recette["serveur_a"], recette["serveur_b"]} <= vus, message(
        en=(
            f"After a reload following the return to nominal, only {sorted(vus)} "
            "answer. The return spoke to the socket but left the state file on "
            "the old decision: the next reload brings it back."
        ),
        fr=(
            f"Après un rechargement qui suit le retour au nominal, seuls "
            f"{sorted(vus)} répondent. Le retour a parlé au socket mais a laissé "
            "le fichier d'état sur l'ancienne décision : le prochain "
            "rechargement la ressort."
        ),
    )

    contenu = edge.run(f"cat {recette['dossier']} 2>/dev/null").stdout
    assert len(contenu) >= 400, message(
        en=(
            f"{recette['dossier']} is missing, empty or too short "
            f"({len(contenu)} characters)."
        ),
        fr=(
            f"{recette['dossier']} est absent, vide ou trop court "
            f"({len(contenu)} caractères)."
        ),
    )
    minuscules = contenu.lower()
    for sujet, motifs in (
        ("la voie employée pour agir", ("socket", "runtime")),
        ("ce qui rend la décision durable", ("state", "etat", "état", "fichier")),
    ):
        assert any(motif in minuscules for motif in motifs), message(
            en=(
                f"{recette['dossier']} does not state {sujet}. The dossier is "
                "what lets the next person undo a decision they did not take."
            ),
            fr=(
                f"{recette['dossier']} ne dit pas {sujet}. Le dossier est ce qui "
                "permet au suivant de défaire une décision qu'il n'a pas prise."
            ),
        )
