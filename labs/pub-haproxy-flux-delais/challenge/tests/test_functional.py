"""Verify that each slow phase has its own bound, that long streams survive
the application's silences, that the session policy holds and its limits are
stated, and that a lost response is not written twice.

CE QUE LE SETUP POSE : deux instances avec leur memoire propre, un flux dont
le battement est lent, un WebSocket silencieux, un point d'ecriture qui
compte puis ferme sans repondre, et un proxy dont toutes les bornes valent
la meme chose.

CE QUE MESURE LE PREMIER CONTROLE : DES DUREES, PAS DES DIRECTIVES

Trois phases peuvent rendre le meme code et le meme message. Ce qui les
distingue, pour qui regarde un incident, est le TEMPS qu'elles prennent. Le
test joue donc les trois separement, mesure les trois durees, et exige
qu'elles soient distinctes autant que les bornes de la recette. Une
configuration ou les trois durent pareil porte une seule borne deguisee en
trois, quelles que soient les lignes ecrites.

CE QUE MESURE LE QUATRIEME : LE COMPTEUR DU BACKEND

Le client ne recoit rien : c'est la definition de la panne jouee. Lui
demander ce qui s'est passe n'a donc aucun sens, et seul le backend peut dire
combien de fois le travail a eu lieu.
"""

from __future__ import annotations

import time
import unicodedata

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-flux-delais/recette.txt"


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
        "timeout_connexion",
        "tentatives",
        "timeout_file",
        "timeout_serveur",
        "duree_flux",
        "battement",
        "timeout_tunnel",
        "route_injection_connexion",
        "route_injection_file",
        "route_bascule",
        "route_lent",
        "route_sse",
        "route_ws",
        "route_ecrire",
        "route_session_ouvrir",
        "route_session_lire",
        "compteur_a",
        "compteur_b",
        "backend_applicatif",
        "serveur_a",
        "serveur_b",
        "dossier",
        "socket_admin",
    )
    return {cle: _valeur(edge, cle) for cle in cles}


def _mesurer(poste, ip: str, chemin: str, plafond: int) -> tuple[float, str]:
    """Rend la durée et le code. La durée est la mesure, le code l'indice."""
    sortie = poste.run(
        f"curl -s -o /dev/null -w '%{{time_total}} %{{http_code}}' "
        f"--max-time {plafond} http://{ip}{chemin}"
    ).stdout.split()
    if len(sortie) != 2:
        return float(plafond), "000"
    return float(sortie[0]), sortie[1]


def _ecritures(edge, recette) -> int:
    total = 0
    for cle in ("compteur_a", "compteur_b"):
        brut = edge.run(f"curl -s --max-time 5 {recette[cle]}").stdout.strip()
        assert brut.isdigit(), message(
            en=f"The counter {recette[cle]} returned {brut!r}.",
            fr=f"Le compteur {recette[cle]} a rendu {brut!r}.",
        )
        total += int(brut)
    return total


def _piloter(edge, recette, commande: str) -> str:
    return edge.run(
        f"echo '{commande}' | sudo socat -t3 stdio {recette['socket_admin']}"
    ).stdout


def test_chaque_phase_lente_a_sa_propre_borne(poste, recette, ip_edge) -> None:
    """Les trois durées, mesurées séparément, et distinctes entre elles."""
    budget_connexion = int(recette["timeout_connexion"]) * int(
        recette["tentatives"]
    )
    budget_file = int(recette["timeout_file"])
    budget_serveur = int(recette["timeout_serveur"])

    duree, statut = _mesurer(
        poste, ip_edge, recette["route_injection_connexion"], budget_connexion + 25
    )
    assert abs(duree - budget_connexion) <= 3, message(
        en=(
            f"A connection to an address that never answers took {duree:.1f}s, "
            f"expected about {budget_connexion}s "
            f"({recette['timeout_connexion']}s x {recette['tentatives']} "
            f"attempts). Status: {statut}."
        ),
        fr=(
            f"Une connexion vers une adresse qui ne répond jamais a pris "
            f"{duree:.1f} s, on en attend environ {budget_connexion} "
            f"({recette['timeout_connexion']} s x {recette['tentatives']} "
            f"tentatives). Code : {statut}."
        ),
    )
    connexion = duree

    # LA FILE. On occupe la seule place du serveur avec une requete longue,
    # puis on en envoie une seconde : elle attend dans la file du backend, et
    # c'est cette attente-la qui a sa propre borne.
    poste.run(
        f"nohup curl -s -o /dev/null --max-time {budget_serveur + 40} "
        f"'http://{ip_edge}{recette['route_injection_file']}"
        f"?duree={budget_file + 25}' >/dev/null 2>&1 &"
    )
    time.sleep(3)
    try:
        duree, statut = _mesurer(
            poste,
            ip_edge,
            f"{recette['route_injection_file']}?duree=1",
            budget_file + 25,
        )
        assert abs(duree - budget_file) <= 4, message(
            en=(
                f"A request waiting for a server whose only slot is taken took "
                f"{duree:.1f}s, expected about {budget_file}s. Without its own "
                "bound, queueing falls back on the connection bound, and a full "
                "queue becomes indistinguishable from an unreachable server. "
                f"Status: {statut}."
            ),
            fr=(
                f"Une requête qui attend un serveur dont la seule place est "
                f"prise a pris {duree:.1f} s, on en attend environ "
                f"{budget_file}. Sans borne propre, l'attente en file retombe "
                "sur la borne de connexion, et une file pleine devient "
                f"indiscernable d'un serveur injoignable. Code : {statut}."
            ),
        )
        file_attente = duree
    finally:
        # `[i]njection` et non `injection` : `pkill -f` compare le motif a la
        # ligne de commande complete, celle du shell qui le porte comprise.
        # Ecrit en clair, le motif se trouve lui-meme, tue son propre parent,
        # et la session SSH meurt : testinfra leve alors un code 255 et c'est
        # le NETTOYAGE qui fait echouer le test. Les crochets ne changent pas
        # ce que l'expression reconnait.
        poste.run("pkill -f '[i]njection/file' || true")

    duree, statut = _mesurer(
        poste,
        ip_edge,
        f"{recette['route_lent']}?duree={budget_serveur + 25}",
        budget_serveur + 30,
    )
    assert abs(duree - budget_serveur) <= 4, message(
        en=(
            f"A response slower than its bound took {duree:.1f}s, expected about "
            f"{budget_serveur}s. Status: {statut}."
        ),
        fr=(
            f"Une réponse plus lente que sa borne a pris {duree:.1f} s, on en "
            f"attend environ {budget_serveur}. Code : {statut}."
        ),
    )
    assert statut == "504", message(
        en=(
            f"A response that exceeded its bound answered {statut}, expected 504. "
            "The code is the second half of the diagnosis: the duration says "
            "which bound, the code says which side gave up."
        ),
        fr=(
            f"Une réponse qui a dépassé sa borne a rendu {statut}, on attend 504. "
            "Le code est la seconde moitié du diagnostic : la durée dit quelle "
            "borne, le code dit quel côté a renoncé."
        ),
    )
    serveur = duree

    durees = {
        "connexion": connexion,
        "file": file_attente,
        "serveur": serveur,
    }
    for gauche in durees:
        for droite in durees:
            if gauche >= droite:
                continue
            assert abs(durees[gauche] - durees[droite]) >= 3, message(
                en=(
                    f"The {gauche} and {droite} phases take the same time "
                    f"({durees[gauche]:.1f}s and {durees[droite]:.1f}s). Three "
                    "identical durations is one bound disguised as three: at "
                    "three in the morning, the elapsed time is what says which "
                    f"phase is slow. All measurements: {durees}."
                ),
                fr=(
                    f"Les phases {gauche} et {droite} prennent le même temps "
                    f"({durees[gauche]:.1f} s et {durees[droite]:.1f} s). Trois "
                    "durées identiques, c'est une seule borne déguisée en trois : "
                    "à trois heures du matin, c'est le temps écoulé qui dit "
                    f"quelle phase est lente. Mesures : {durees}."
                ),
            )


def test_les_flux_longs_tiennent_la_duree_annoncee(poste, recette, ip_edge) -> None:
    """Le flux d'événements et le WebSocket, à travers les silences."""
    duree = int(recette["duree_flux"])
    battement = int(recette["battement"])

    sortie = poste.run(
        f"flux-sse {ip_edge} '{recette['route_sse']}?duree={duree}' {duree}"
    ).stdout
    arrivees = []
    for ligne in sortie.splitlines():
        morceaux = ligne.split(" ", 1)
        if len(morceaux) == 2:
            try:
                arrivees.append(float(morceaux[0]))
            except ValueError:
                continue
    attendus = max(2, duree // battement)
    assert len(arrivees) >= attendus, message(
        en=(
            f"The event stream returned {len(arrivees)} events in {duree}s, "
            f"expected at least {attendus} with a {battement}s heartbeat. An "
            "inactivity bound shorter than the application's silence cuts a "
            f"stream that was perfectly healthy. Output:\n{sortie[:400]}"
        ),
        fr=(
            f"Le flux d'événements a rendu {len(arrivees)} événements en "
            f"{duree} s, on en attend au moins {attendus} avec un battement de "
            f"{battement} s. Une borne d'inactivité plus courte que le silence "
            "de l'application coupe un flux qui se portait parfaitement bien. "
            f"Sortie :\n{sortie[:400]}"
        ),
    )
    assert arrivees[-1] - arrivees[0] >= duree - battement - 3, message(
        en=(
            f"The events span {arrivees[-1] - arrivees[0]:.1f}s, but the stream "
            f"was asked for {duree}s. It was cut before its end."
        ),
        fr=(
            f"Les événements s'étalent sur {arrivees[-1] - arrivees[0]:.1f} s, "
            f"alors que le flux a été demandé pour {duree} s. Il a été coupé "
            "avant son terme."
        ),
    )

    sortie = poste.run(f"client-ws {ip_edge} {duree}").stdout
    assert "POIGNEE ok" in sortie, message(
        en=f"The WebSocket handshake did not complete:\n{sortie[:400]}",
        fr=f"La poignée de main WebSocket n'a pas abouti :\n{sortie[:400]}",
    )
    assert "DEBUT echo:debut" in sortie, message(
        en=f"The WebSocket did not echo the first message:\n{sortie[:400]}",
        fr=f"Le WebSocket n'a pas renvoyé le premier message :\n{sortie[:400]}",
    )
    assert "APRES echo:apres" in sortie, message(
        en=(
            f"The WebSocket no longer answers after {duree}s of silence:\n"
            f"{sortie[:400]}\nOnce the connection is upgraded, it is the tunnel "
            "bound that decides how long a silent conversation survives, and no "
            "other setting replaces it. A WebSocket is silent by design: a "
            "chat window open with nobody typing exchanges nothing for minutes."
        ),
        fr=(
            f"Le WebSocket ne répond plus après {duree} s de silence :\n"
            f"{sortie[:400]}\nUne fois la connexion basculée, c'est la borne de "
            "tunnel qui décide combien de temps une conversation silencieuse "
            "survit, et aucun autre réglage ne la remplace. Un WebSocket est "
            "silencieux par nature : une fenêtre de discussion ouverte sans "
            "personne qui écrit n'échange rien pendant des minutes."
        ),
    )


def test_la_politique_de_session_tient_et_ses_limites_sont_dites(
    edge, poste, recette, ip_edge
) -> None:
    """Vingt lectures trouvent la session, et son retrait la perd."""
    biscuits = "/tmp/biscuits-flux-delais"
    poste.run(f"rm -f {biscuits}")
    ouverture = poste.run(
        f"curl -s -c {biscuits} --max-time 10 "
        f"http://{ip_edge}{recette['route_session_ouvrir']}"
    ).stdout
    assert "session ouverte sur" in ouverture, message(
        en=f"No session was opened ({ouverture.strip()[:160]!r}).",
        fr=f"Aucune session n'a été ouverte ({ouverture.strip()[:160]!r}).",
    )
    instance = ouverture.split("sur")[-1].strip()
    connus = (recette["serveur_a"], recette["serveur_b"])
    assert instance in connus, message(
        en=(
            f"The instance that opened the session calls itself {instance!r}, "
            f"which is not one of the server names the recipe prescribes "
            f"({connus}). The runtime socket addresses a server by its NAME, so "
            "those names are part of the contract: the validation takes out of "
            "service the one holding the session."
        ),
        fr=(
            f"L'instance qui a ouvert la session s'annonce {instance!r}, qui "
            f"n'est pas un des noms de serveurs que la recette prescrit "
            f"({connus}). Le socket d'administration adresse un serveur par son "
            "NOM, donc ces noms font partie du contrat : la validation retire du "
            "service celui qui détient la session."
        ),
    )

    echecs = []
    for essai in range(20):
        lecture = poste.run(
            f"curl -s -b {biscuits} -o /dev/null -w '%{{http_code}}' "
            f"--max-time 10 http://{ip_edge}{recette['route_session_lire']}"
        ).stdout.strip()
        if lecture != "200":
            echecs.append((essai, lecture))
    assert not echecs, message(
        en=(
            f"{len(echecs)} of 20 reads lost the session (first failures: "
            f"{echecs[:3]}). Without a session policy, one request in two "
            "changes instance, and the state the client believes it has is not "
            "there. The session lives in the instance that created it."
        ),
        fr=(
            f"{len(echecs)} lectures sur 20 ont perdu la session (premiers "
            f"échecs : {echecs[:3]}). Sans politique de session, une requête sur "
            "deux change d'instance, et l'état que le client croit avoir n'y est "
            "pas. La session vit dans l'instance qui l'a créée."
        ),
    )

    # LA LIMITE, MESUREE. Retirer du service l'instance qui detient la
    # session la perd : coller un client a une instance n'est pas repliquer
    # son etat. Ce n'est pas un defaut a corriger, c'est une propriete a
    # connaitre, et le dossier doit la dire.
    _piloter(
        edge, recette, f"set server {recette['backend_applicatif']}/{instance} state maint"
    )
    try:
        time.sleep(2)
        apres = poste.run(
            f"curl -s -b {biscuits} -o /dev/null -w '%{{http_code}}' "
            f"--max-time 10 http://{ip_edge}{recette['route_session_lire']}"
        ).stdout.strip()
        assert apres == "409", message(
            en=(
                f"With instance {instance} out of service, the read answered "
                f"{apres}, expected 409. Either the request was not moved to the "
                "other instance, or the session is not where the lab says it is."
            ),
            fr=(
                f"L'instance {instance} étant hors service, la lecture a répondu "
                f"{apres}, on attend 409. Soit la requête n'a pas été déplacée "
                "vers l'autre instance, soit la session n'est pas là où le lab "
                "le dit."
            ),
        )
    finally:
        _piloter(
            edge,
            recette,
            f"set server {recette['backend_applicatif']}/{instance} state ready",
        )

    contenu = edge.run(f"cat {recette['dossier']} 2>/dev/null").stdout
    assert len(contenu) >= 400, message(
        en=(
            f"{recette['dossier']} is missing, empty or too short "
            f"({len(contenu)} characters). The recipe asks for the limits of "
            "the session policy, and they are not readable in the configuration."
        ),
        fr=(
            f"{recette['dossier']} est absent, vide ou trop court "
            f"({len(contenu)} caractères). La recette demande les limites de la "
            "politique de session, et elles ne se lisent pas dans la "
            "configuration."
        ),
    )
    # LES ACCENTS SONT RETIRES AVANT DE CHERCHER, et on cherche des
    # RACINES. Mesure du 2026-10-26 : un dossier qui disait « coller n'est
    # pas repliquer » et « toute mise a jour tournante deconnecte les
    # sessions en cours » etait refuse, parce que le motif « replic » ne se
    # trouve pas dans « repliquer » ecrit avec son accent, ni « perdue »
    # dans « se perd ». Un controle de texte libre qui exige des formes
    # flechies exactes rejette un texte juste, et pousse a ecrire pour le
    # test plutot que pour le lecteur.
    minuscules = unicodedata.normalize("NFD", contenu.lower())
    minuscules = "".join(c for c in minuscules if not unicodedata.combining(c))
    assert any(
        motif in minuscules
        # Des motifs qui designent LE SUJET, et non n'importe quel
        # emploi du verbe retirer : « le cookie est retire avant
        # transmission » ne dit rien de ce qui arrive a une session quand
        # son instance s'en va.
        for motif in ("replic", "quitte le service", "hors service",
                      "maintenance", "session perdue", "sessions perdues",
                      "perte de session", "mise a jour tournante")
    ), message(
        en=(
            f"{recette['dossier']} does not say what happens to a session when "
            "its instance leaves service. Pinning is not replication, and that "
            "is the sentence an operator needs before a rolling update."
        ),
        fr=(
            f"{recette['dossier']} ne dit pas ce qu'il advient d'une session "
            "quand son instance quitte le service. Coller n'est pas répliquer, "
            "et c'est la phrase dont un exploitant a besoin avant une mise à "
            "jour tournante."
        ),
    )


def test_aucune_ecriture_n_est_dupliquee(edge, poste, recette, ip_edge) -> None:
    """CRITIQUE : une seule tentative, un seul travail, et les lectures tiennent.

    Le client ne reçoit rien : c'est la définition de la panne jouée. Lui
    demander ce qui s'est passé n'a donc aucun sens, et seul le backend peut
    dire combien de fois le travail a eu lieu.
    """
    avant = _ecritures(edge, recette)
    sortie = poste.run(
        f"ecrire-une-fois {ip_edge} {recette['route_ecrire']}"
    ).stdout
    time.sleep(3)
    apres = _ecritures(edge, recette)

    assert apres - avant == 1, message(
        en=(
            f"One write attempt produced {apres - avant} writes. The endpoint "
            "counts the write THEN closes without answering: the work happened, "
            "and the client cannot know. A proxy that replays what it can "
            f"replays that one too. Client said: {sortie.strip()[:120]!r}"
        ),
        fr=(
            f"Une seule tentative d'écriture a produit {apres - avant} écritures. "
            "Le point d'écriture compte l'écriture PUIS ferme sans répondre : le "
            "travail a eu lieu, et le client ne peut pas le savoir. Un proxy qui "
            "rejoue ce qu'il peut rejoue celle-là aussi. Le client a dit : "
            f"{sortie.strip()[:120]!r}"
        ),
    )

    # LA MOITIE QUI COMPTE. Restreindre les reessais n'est pas les
    # supprimer : une lecture dont la connexion echoue doit encore aboutir,
    # sinon la configuration a perdu sa tolerance aux pannes en gagnant sa
    # surete.
    echecs = []
    for essai in range(6):
        statut = poste.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 30 "
            f"http://{ip_edge}{recette['route_bascule']}"
        ).stdout.strip()
        if statut != "200":
            echecs.append((essai, statut))
    assert not echecs, message(
        en=(
            f"{len(echecs)} of 6 reads failed on a backend with one dead server "
            f"and one healthy one ({echecs[:3]}). Restricting retries is not "
            "removing them: a read whose connection fails must still reach the "
            "server that is up."
        ),
        fr=(
            f"{len(echecs)} lectures sur 6 ont échoué sur un backend qui porte un "
            f"serveur mort et un serveur sain ({echecs[:3]}). Restreindre les "
            "réessais n'est pas les supprimer : une lecture dont la connexion "
            "échoue doit encore atteindre le serveur qui répond."
        ),
    )
