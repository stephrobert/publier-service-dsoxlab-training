"""Verify the starting state, that the delivery switches generation without
cutting short traffic nor an established flow, that the rollback restores it,
that the journal says what was measured, and that it all survives a reboot.

CE QUE LE SETUP POSE : la generation 1.4.2 en service, la 1.5.0 disponible
et arretee, et AUCUN moyen de passer de l'une a l'autre.

LA VALIDATION PILOTE, ELLE N'OBSERVE PAS

Les controles 2 et 3 executent `livrer` et `revenir` et mesurent ENTRE les
appels. Une bascule ne se constate pas apres coup : une fois qu'elle est
faite, rien ne distingue un service bascule sans coupure d'un service
bascule avec une coupure de trois secondes, et c'est precisement la
difference qui compte.

LE PID DU MAITRE EST LA MESURE QU'AUCUN CLIENT NE PEUT FAIRE

Le processus maitre de HAProxy tient les sockets d'ecoute. Le remplacer
ferme le port le temps qu'un autre l'ouvre, et une sonde qui tire une
requete toutes les 200 ms peut tout a fait ne rien voir. On lit donc le PID
avant et apres, sur la machine.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
MANIFESTE = "/opt/pub-haproxy-mise-a-jour/manifeste.txt"


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
    sortie = edge.run(f"grep -oP '(?<=^{cle} = ).*' {MANIFESTE}").stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def _valeur(edge, cle: str) -> str:
    lues = _lignes(edge, cle)
    assert len(lues) == 1, message(
        en=f"The manifest {MANIFESTE} declares {len(lues)} `{cle}`, expected one.",
        fr=f"Le manifeste {MANIFESTE} déclare {len(lues)} `{cle}`, on en attend un.",
    )
    return lues[0]


@pytest.fixture(scope="module")
def manifeste(edge) -> dict:
    generations = {}
    for ligne in _lignes(edge, "generation"):
        version, port = ligne.split()
        generations[version] = int(port)
    return {
        "generations": generations,
        "depart": _valeur(edge, "depart"),
        "livrer": _valeur(edge, "livrer"),
        "revenir": _valeur(edge, "revenir"),
        "journal": _valeur(edge, "journal"),
    }


def _version_servie(poste, ip: str) -> str:
    corps = poste.run(f"curl -s --max-time 10 http://{ip}/").stdout
    for ligne in corps.splitlines():
        if ligne.startswith("pub-haproxy-mise-a-jour version "):
            return ligne.rsplit(" ", 1)[-1]
    return f"indeterminee ({corps.strip()[:120]!r})"


def _maitre(edge) -> str:
    return edge.run("systemctl show -p MainPID --value haproxy").stdout.strip()


def _ouvriers(edge) -> set[str]:
    maitre = _maitre(edge)
    if not maitre or maitre == "0":
        return set()
    sortie = edge.run(f"pgrep -P {maitre} 2>/dev/null").stdout
    return {pid.strip() for pid in sortie.split() if pid.strip()}


def _lire(poste, chemin: str) -> list[str]:
    return [
        ligne.strip()
        for ligne in poste.run(f"cat {chemin} 2>/dev/null").stdout.splitlines()
        if ligne.strip()
    ]


def _attendre_fin(poste, chemin: str, limite_s: float) -> bool:
    limite = time.monotonic() + limite_s
    while time.monotonic() < limite:
        if "fin" in _lire(poste, chemin):
            return True
        time.sleep(1)
    return False


def _bascule(edge, poste, ip_edge, manifeste, commande: str, attendue: str) -> None:
    """Joue une bascule et mesure PENDANT, pas apres.

    Le flux long est ouvert AVANT, la sonde courte tourne PENDANT, et les
    PID sont lus des deux cotes du geste. C'est la seule facon de
    distinguer une bascule sans coupure d'une bascule avec coupure : une
    fois faite, les deux se ressemblent.
    """
    flux = "/tmp/flux-maj.txt"
    sonde = "/tmp/sonde-maj.txt"
    poste.run(f"rm -f {flux} {sonde}")

    poste.run(f"nohup flux-long {ip_edge} {flux} >/dev/null 2>&1 &")
    debut = time.monotonic()
    while time.monotonic() - debut < 25:
        if len(_lire(poste, flux)) >= 2:
            break
        time.sleep(1)
    lignes_avant = _lire(poste, flux)
    assert len(lignes_avant) >= 2, message(
        en=f"The long flow did not start: {lignes_avant}",
        fr=f"Le flux long n'a pas démarré : {lignes_avant}",
    )
    generation_du_flux = lignes_avant[0]

    poste.run(f"nohup sonde-courte {ip_edge} {sonde} 120 >/dev/null 2>&1 &")
    time.sleep(2)

    maitre_avant = _maitre(edge)
    ouvriers_avant = _ouvriers(edge)
    assert maitre_avant and maitre_avant != "0", message(
        en="HAProxy is not running before the switch.",
        fr="HAProxy ne tourne pas avant la bascule.",
    )

    lancement = edge.run(f"sudo {commande} 2>&1")
    assert lancement.rc == 0, message(
        en=f"{commande} failed (code {lancement.rc}): {lancement.stdout.strip()[-400:]!r}",
        fr=f"{commande} a échoué (code {lancement.rc}) : {lancement.stdout.strip()[-400:]!r}",
    )

    maitre_apres = _maitre(edge)
    assert maitre_apres == maitre_avant, message(
        en=(
            f"The HAProxy master changed ({maitre_avant} then {maitre_apres}). "
            "It holds the listening sockets: replacing it closes the port for "
            "as long as another takes it, and a probe firing every 200 ms can "
            "miss it entirely. A configuration change is applied with a reload, "
            "not a restart."
        ),
        fr=(
            f"Le maître HAProxy a changé ({maitre_avant} puis {maitre_apres}). "
            "C'est lui qui tient les sockets d'écoute : le remplacer ferme le "
            "port le temps qu'un autre le reprenne, et une sonde qui tire toutes "
            "les 200 ms peut très bien ne rien voir. Un changement de "
            "configuration s'applique par un rechargement, pas par un "
            "redémarrage."
        ),
    )

    ouvriers_apres = _ouvriers(edge)
    assert ouvriers_apres - ouvriers_avant, message(
        en=(
            f"No new worker appeared after the switch (before {sorted(ouvriers_avant)}, "
            f"after {sorted(ouvriers_apres)}). The configuration was not reloaded."
        ),
        fr=(
            f"Aucun nouvel ouvrier n'est apparu après la bascule (avant "
            f"{sorted(ouvriers_avant)}, après {sorted(ouvriers_apres)}). La "
            "configuration n'a pas été rechargée."
        ),
    )

    assert _attendre_fin(poste, sonde, 60), message(
        en="The short probe did not finish within 60s.",
        fr="La sonde courte ne s'est pas terminée dans les 60 s.",
    )
    mesures = [ligne for ligne in _lire(poste, sonde) if ligne != "fin"]
    echecs = [ligne for ligne in mesures if ligne != "200"]
    assert len(echecs) <= 1, message(
        en=(
            f"{len(echecs)} short requests of {len(mesures)} failed during the "
            f"switch ({echecs[:5]}). The plan allows at most one."
        ),
        fr=(
            f"{len(echecs)} requêtes courtes sur {len(mesures)} ont échoué pendant "
            f"la bascule ({echecs[:5]}). Le plan en tolère une au plus."
        ),
    )

    assert _attendre_fin(poste, flux, 150), message(
        en=(
            "The long flow opened before the switch never reached its end. A "
            "reload keeps old workers alive to finish the connections they "
            "hold: cutting it means the generation it talks to was stopped too "
            "early, or the switch was a restart."
        ),
        fr=(
            "Le flux long ouvert avant la bascule n'est jamais allé à son terme. "
            "Un rechargement garde les anciens ouvriers en vie pour finir les "
            "connexions qu'ils tiennent : le couper signifie que la génération à "
            "laquelle ils parlaient a été arrêtée trop tôt, ou que la bascule "
            "était un redémarrage."
        ),
    )
    lignes_apres = _lire(poste, flux)
    assert len(lignes_apres) > len(lignes_avant) + 3, message(
        en=(
            f"The long flow received {len(lignes_apres)} lines in total against "
            f"{len(lignes_avant)} before the switch: it stopped receiving."
        ),
        fr=(
            f"Le flux long a reçu {len(lignes_apres)} lignes en tout contre "
            f"{len(lignes_avant)} avant la bascule : il a cessé de recevoir."
        ),
    )
    assert "erreur" not in " ".join(lignes_apres), message(
        en=f"The long flow reported an error: {lignes_apres[-2:]}",
        fr=f"Le flux long a signalé une erreur : {lignes_apres[-2:]}",
    )
    # Le flux etabli reste servi par la generation qui l'a pris, et c'est
    # normal : les anciens ouvriers lui parlent encore. C'est aussi pourquoi
    # une livraison ne retire pas la generation qu'elle remplace.
    assert generation_du_flux.split()[-1] in " ".join(lignes_apres), message(
        en="The long flow changed generation mid-stream, which cannot happen cleanly.",
        fr="Le flux long a changé de génération en cours de route, ce qui ne peut pas se faire proprement.",
    )

    servie = _version_servie(poste, ip_edge)
    assert servie == attendue, message(
        en=f"After the switch, the service returns {servie!r}, expected {attendue!r}.",
        fr=f"Après la bascule, le service rend {servie!r}, on attend {attendue!r}.",
    )



def _attendre_retour(machine, limite_s: float = 180.0) -> bool:
    """Attend qu'une machine redemarree reponde de nouveau.

    `testinfra` LEVE quand la connexion SSH echoue, au lieu de rendre un
    resultat en echec. Une machine absente pendant son redemarrage n'est
    pourtant pas une erreur de test : c'est l'etat qu'on attend. On traite
    donc l'exception comme une reponse negative, et on reessaie.

    Mesure du 2026-10-26 : sans cette tolerance, le test echoue en 22
    secondes au lieu d'attendre, sur un `Connection refused` qui signifie
    seulement que sshd n'ecoute pas encore.
    """
    limite = time.monotonic() + limite_s
    while time.monotonic() < limite:
        try:
            resultat = machine.run("echo up")
        except Exception:  # noqa: BLE001 - toute panne de transport vaut « pas encore »
            time.sleep(5)
            continue
        if resultat.rc == 0 and "up" in resultat.stdout:
            return True
        time.sleep(5)
    return False

def test_l_etat_de_depart_et_les_deux_executables(
    edge, poste, manifeste, ip_edge
) -> None:
    """La génération de départ, et ce que l'apprenant devait livrer."""
    servie = _version_servie(poste, ip_edge)
    assert servie == manifeste["depart"], message(
        en=f"The service returns {servie!r}, the manifest announces {manifeste['depart']!r}.",
        fr=f"Le service rend {servie!r}, le manifeste annonce {manifeste['depart']!r}.",
    )
    for cle in ("livrer", "revenir"):
        chemin = manifeste[cle]
        droits = edge.run(f"test -x {chemin} && echo oui || echo non").stdout.strip()
        assert droits == "oui", message(
            en=(
                f"{chemin} is missing or not executable. The validation runs it: "
                "a switch is not observed afterwards, it is played."
            ),
            fr=(
                f"{chemin} est absent ou non exécutable. La validation l'exécute : "
                "une bascule ne se constate pas après coup, elle se joue."
            ),
        )
    assert _maitre(edge) not in ("", "0"), message(
        en="HAProxy is not running at the start of the measurement.",
        fr="HAProxy ne tourne pas au début de la mesure.",
    )


def test_la_livraison_bascule_sans_couper(edge, poste, manifeste, ip_edge) -> None:
    """La bascule vers la nouvelle génération, mesurée pendant qu'elle a lieu."""
    cible = [v for v in manifeste["generations"] if v != manifeste["depart"]]
    assert len(cible) == 1, message(
        en=f"The manifest does not describe exactly two generations: {manifeste['generations']}",
        fr=f"Le manifeste ne décrit pas exactement deux générations : {manifeste['generations']}",
    )
    _bascule(
        edge, poste, ip_edge, manifeste,
        f"{manifeste['livrer']} {cible[0]}", cible[0],
    )


def test_le_retour_restaure_la_generation(edge, poste, manifeste, ip_edge) -> None:
    """CRITIQUE : le retour est une bascule comme l'autre, et se mesure pareil.

    Un retour arrière qui coupe le service n'en est pas un : on l'exécute
    précisément quand quelque chose va déjà mal, et c'est le moment où une
    coupure supplémentaire coûte le plus cher.
    """
    _bascule(
        edge, poste, ip_edge, manifeste,
        manifeste["revenir"], manifeste["depart"],
    )


def test_le_journal_dit_ce_qui_a_ete_mesure(edge, manifeste) -> None:
    """Relu par un humain. Le test vérifie la présence et deux sujets."""
    contenu = edge.run(f"cat {manifeste['journal']} 2>/dev/null").stdout
    assert len(contenu) >= 400, message(
        en=(
            f"{manifeste['journal']} is missing, empty or too short "
            f"({len(contenu)} characters)."
        ),
        fr=(
            f"{manifeste['journal']} est absent, vide ou trop court "
            f"({len(contenu)} caractères)."
        ),
    )
    minuscules = contenu.lower()
    for sujet, motifs in (
        ("le flux long ou les connexions établies", ("flux", "connexion", "longue")),
        ("comment revenir", ("revenir", "retour", "rollback")),
    ):
        assert any(motif in minuscules for motif in motifs), message(
            en=f"{manifeste['journal']} does not cover {sujet}.",
            fr=f"{manifeste['journal']} ne traite pas {sujet}.",
        )


def test_tout_revient_apres_un_redemarrage(edge, poste, manifeste, ip_edge) -> None:
    """CRITIQUE, et dernier : il coupe la machine, puis REJOUE une livraison.

    Une livraison qui n'a laissé sa trace que dans la mémoire du processus
    disparaît ici, et nulle part avant.

    POURQUOI LA LIVRAISON EST REJOUÉE APRÈS

    Sans ce second temps, ce test passait sur l'état de départ : la
    génération 1.4.2 y est déjà servie et son unité déjà activée, donc elle
    revient d'elle-même après un redémarrage. Le lab donnait 20 points sur
    100 à qui n'avait rien fait. Mesuré le 2026-10-26.

    Ce que le plan promet n'est pas qu'un service redémarre, c'est que le
    CYCLE reste opérant après un redémarrage. On le mesure donc en le
    jouant : une bascule complète, puis le retour.
    """
    for cle in ("livrer", "revenir"):
        chemin = manifeste[cle]
        droits = edge.run(f"test -x {chemin} && echo oui || echo non").stdout.strip()
        assert droits == "oui", message(
            en=(
                f"{chemin} is missing or not executable before the reboot: "
                "there is no cycle to put to the test."
            ),
            fr=(
                f"{chemin} est absent ou non exécutable avant le redémarrage : "
                "il n'y a aucun cycle à éprouver."
            ),
        )

    avant = _version_servie(poste, ip_edge)
    assert avant == manifeste["depart"], message(
        en=f"Before the reboot, the service returns {avant!r}.",
        fr=f"Avant le redémarrage, le service rend {avant!r}.",
    )

    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)

    revenu = _attendre_retour(edge, 180)
    assert revenu, message(
        en="edge.lab did not come back online within 180s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180 s après le redémarrage.",
    )

    servie = ""
    limite = time.monotonic() + 120
    while time.monotonic() < limite:
        servie = _version_servie(poste, ip_edge)
        if servie == manifeste["depart"]:
            break
        time.sleep(5)
    assert servie == manifeste["depart"], message(
        en=(
            f"After the reboot, the service returns {servie!r}, expected "
            f"{manifeste['depart']!r}. A delivery that only left its trace in "
            "the process's memory disappears here: the generation must be "
            "enabled at boot, and the file HAProxy reads must say the same "
            "thing as what was running."
        ),
        fr=(
            f"Après le redémarrage, le service rend {servie!r}, on attend "
            f"{manifeste['depart']!r}. Une livraison qui n'a laissé sa trace que "
            "dans la mémoire du processus disparaît ici : la génération doit "
            "être activée au démarrage, et le fichier que HAProxy lit doit dire "
            "la même chose que ce qui tournait."
        ),
    )

    # LE CYCLE, REJOUE APRES LE REDEMARRAGE. C'est ce que le plan promet,
    # et c'est ce qu'un service simplement activé ne prouve pas.
    cible = next(v for v in manifeste["generations"] if v != manifeste["depart"])
    _bascule(
        edge, poste, ip_edge, manifeste,
        f"{manifeste['livrer']} {cible}", cible,
    )
    _bascule(
        edge, poste, ip_edge, manifeste,
        manifeste["revenir"], manifeste["depart"],
    )
