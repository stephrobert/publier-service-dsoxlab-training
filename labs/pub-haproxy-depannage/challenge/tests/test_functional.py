"""Verify that the service is restored, that neither canary was disabled to
get there, that administration and backends stay unreachable from the
network, and that the dossier separates the cause from its symptom.

CE QUE LE SETUP POSE : une pile saine, une panne tiree au hasard parmi cinq,
et du bruit qui n'explique rien.

LES TESTS NE CONNAISSENT PAS LA VARIANTE

Ils ne lisent pas le fichier qui la note, et c'est volontaire. Ils rejouent
la recette entiere, ce qui est exactement ce qu'un exploitant fait apres une
astreinte : non pas verifier le geste qui a retabli le service, mais
constater que l'etat attendu est revenu, tout entier.

CE QUE MESURE LE CONTROLE CRITIQUE

Les deux canaris font partie de l'etat SAIN. Retirer `verify required` ou
les sondes ferait repartir le service dans au moins deux des cinq variantes,
et retirerait la garantie en meme temps. Le test exige donc que les deux
tiennent leur role APRES la correction : le canari TLS refuse, le serveur
degrade reste hors service.
"""

from __future__ import annotations

import uuid

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-depannage/recette.txt"
MARQUE = "pub-haproxy-depannage service"


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
def recette(edge) -> dict[str, str]:
    cles = (
        "canari_tls",
        "canari_sonde",
        "port_stats",
        "ports_backends",
        "socket_admin",
        "backend_applicatif",
        "dossier",
    )
    return {cle: _valeur(edge, cle) for cle in cles}


def _depuis_le_client(poste, ip: str, chemin: str) -> tuple[str, str]:
    jeton = uuid.uuid4().hex[:10]
    separateur = "&" if "?" in chemin else "?"
    statut = poste.run(
        f"curl -s -o /tmp/corps-depannage -w '%{{http_code}}' --max-time 20 "
        f"'http://{ip}{chemin}{separateur}jeton={jeton}'"
    ).stdout.strip()
    corps = poste.run("cat /tmp/corps-depannage 2>/dev/null").stdout
    return statut, corps


def _recette_service(edge, poste, ip_edge) -> None:
    """La matrice entière, depuis le client, avec un jeton par mesure.

    Extraite en fonction parce que les deux contrôles de garde l'exigent
    aussi. Un canari qui tient sur un service à terre ne prouve rien : il
    est facile de ne RIEN servir et de ne rien laisser fuir.
    """
    attendus = _lignes(edge, "attendu")
    assert attendus, message(
        en=f"The recipe {RECETTE} declares no expected route.",
        fr=f"La recette {RECETTE} ne déclare aucune route attendue.",
    )
    for ligne in attendus:
        chemin, marqueur = ligne.split()
        statut, corps = _depuis_le_client(poste, ip_edge, chemin)
        assert statut == "200", message(
            en=(
                f"{chemin} answered {statut} from the client, expected 200. The "
                "code is the symptom; the cause is upstream of it, and at least "
                "three of the five families produce this same code."
            ),
            fr=(
                f"{chemin} a répondu {statut} depuis le client, on attend 200. Le "
                "code est le symptôme ; la cause est en amont, et au moins trois "
                "des cinq familles produisent ce même code."
            ),
        )
        assert f"{MARQUE} {marqueur}" in corps, message(
            en=(
                f"{chemin} answers, but not from {marqueur} "
                f"({corps.strip()[:160]!r}). A route that answers is not a route "
                "that reaches the right service."
            ),
            fr=(
                f"{chemin} répond, mais pas depuis {marqueur} "
                f"({corps.strip()[:160]!r}). Une route qui répond n'est pas une "
                "route qui atteint le bon service."
            ),
        )


def test_le_service_et_les_routes_saines_sont_restaures(
    edge, poste, recette, ip_edge
) -> None:
    """La recette entière, rejouée depuis le client indépendant."""
    _recette_service(edge, poste, ip_edge)


def test_les_verifications_ne_sont_pas_desactivees(
    edge, poste, recette, ip_edge
) -> None:
    """CRITIQUE : les deux canaris tiennent leur rôle, SERVICE RÉTABLI.

    Le service d'abord. Les deux canaris font partie de l'état sain, donc
    ils tiennent déjà AVANT la panne dans quatre des cinq variantes : ce
    test donnait 2 points sur 4 à qui n'avait rien fait. Mesuré le
    2026-10-26.

    Ce qu'il mesure vraiment est une conjonction : le service est revenu ET
    il l'est sans qu'on ait désactivé ce qui le protège. Prises séparément,
    les deux moitiés sont faciles ; c'est leur rencontre qui est le travail.
    """
    _recette_service(edge, poste, ip_edge)
    statut, corps = _depuis_le_client(poste, ip_edge, recette["canari_tls"])
    assert statut in ("502", "503"), message(
        en=(
            f"The TLS canary {recette['canari_tls']} answered {statut}, expected "
            f"502 or 503 ({corps.strip()[:120]!r}). It leads to a backend whose "
            "certificate is signed by a foreign authority and which carries the "
            "same name as the legitimate one, and it serves the same marker. Its "
            "refusal is the only thing that proves verification is strict: "
            "disabling verification brings the service back and removes the "
            "proof in the same gesture."
        ),
        fr=(
            f"Le canari TLS {recette['canari_tls']} a répondu {statut}, on attend "
            f"502 ou 503 ({corps.strip()[:120]!r}). Il mène à un backend dont le "
            "certificat est signé par une autorité étrangère et qui porte le même "
            "nom que le légitime, et il sert le même marqueur. Son refus est la "
            "seule chose qui prouve que la vérification est stricte : la "
            "désactiver fait repartir le service et retire la preuve du même "
            "geste."
        ),
    )

    brut = edge.run(
        f"echo 'show stat' | sudo socat -t3 stdio {recette['socket_admin']}"
    ).stdout
    lignes = [ligne for ligne in brut.splitlines() if ligne.strip()]
    assert lignes and lignes[0].startswith("#"), message(
        en=f"`show stat` returned nothing usable: {brut.strip()[:160]!r}",
        fr=f"`show stat` n'a rien rendu d'exploitable : {brut.strip()[:160]!r}",
    )
    colonnes = lignes[0].lstrip("# ").rstrip(",").split(",")
    serveurs: dict[str, dict[str, str]] = {}
    for ligne in lignes[1:]:
        champs = dict(zip(colonnes, ligne.split(","), strict=False))
        if champs.get("pxname") == recette["backend_applicatif"]:
            serveurs[champs.get("svname", "")] = champs

    degrade = recette["canari_sonde"]
    assert degrade in serveurs, message(
        en=(
            f"The server {degrade} is no longer declared in "
            f"{recette['backend_applicatif']} (seen: {sorted(serveurs)}). "
            "Removing it is not taking it out of service: it is removing the "
            "check that proves the probes work."
        ),
        fr=(
            f"Le serveur {degrade} n'est plus déclaré dans "
            f"{recette['backend_applicatif']} (vus : {sorted(serveurs)}). Le "
            "retirer n'est pas le sortir du service : c'est retirer le contrôle "
            "qui prouve que les sondes fonctionnent."
        ),
    )
    etat = serveurs[degrade].get("status", "")
    assert "UP" not in etat, message(
        en=(
            f"The server {degrade} is {etat!r}. Its readiness fails permanently "
            "and its useful routes return 500: a probe that leaves it in service "
            "is a probe that does not read what it asks for, or no probe at all."
        ),
        fr=(
            f"Le serveur {degrade} est {etat!r}. Sa readiness échoue en "
            "permanence et ses routes utiles rendent 500 : une sonde qui le "
            "laisse en service est une sonde qui ne lit pas ce qu'elle demande, "
            "ou pas de sonde du tout."
        ),
    )

    sains = [
        nom
        for nom, champs in serveurs.items()
        if nom not in ("FRONTEND", "BACKEND", degrade)
        and champs.get("status") == "UP"
    ]
    assert sains, message(
        en=(
            f"No healthy server is UP in {recette['backend_applicatif']}. "
            "Refusing everything is not verifying: the probe must take out what "
            "is broken and leave what works."
        ),
        fr=(
            f"Aucun serveur sain n'est UP dans {recette['backend_applicatif']}. "
            "Refuser tout n'est pas vérifier : la sonde doit retirer ce qui est "
            "cassé et laisser ce qui marche."
        ),
    )


def test_l_administration_et_les_backends_restent_injoignables(
    edge, poste, recette, ip_edge
) -> None:
    """CRITIQUE, mesuré dans les deux sens, et SERVICE RÉTABLI.

    Comme le contrôle précédent : ne rien exposer est trivial sur un
    service à terre. La conjonction est ce qui compte.
    """
    _recette_service(edge, poste, ip_edge)
    ports = [recette["port_stats"], *recette["ports_backends"].split()]
    for port in ports:
        depuis_le_client = poste.run(
            f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time 5 "
            f"http://{ip_edge}:{port}/"
        ).stdout.strip()
        assert depuis_le_client == "000", message(
            en=(
                f"Port {port} answered {depuis_le_client} from the client. The "
                "stats page and the backends belong to the machine: an outage is "
                "not a reason to open them, and a port opened during an incident "
                "is a port nobody closes."
            ),
            fr=(
                f"Le port {port} a répondu {depuis_le_client} depuis le client. La "
                "page d'état et les backends appartiennent à la machine : une "
                "panne n'est pas une raison de les ouvrir, et un port ouvert "
                "pendant un incident est un port que personne ne referme."
            ),
        )

    # LES DEUX MOITIES : ce qui doit rester local doit EXISTER localement.
    local = edge.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"http://127.0.0.1:{recette['port_stats']}/"
    ).stdout.strip()
    assert local.startswith(("200", "401")), message(
        en=(
            f"The stats page answers {local} on the loopback. Not public is not "
            "the same as not there: it is what you read during the next outage."
        ),
        fr=(
            f"La page d'état répond {local} sur la boucle locale. « Pas publique » "
            "n'est pas « pas là » : c'est ce qu'on lit à la panne suivante."
        ),
    )

    sortie = edge.run(f"sudo stat -c '%F %a' {recette['socket_admin']}").stdout.strip()
    assert sortie.startswith("socket"), message(
        en=f"{recette['socket_admin']} is not a UNIX socket ({sortie!r}).",
        fr=f"{recette['socket_admin']} n'est pas un socket UNIX ({sortie!r}).",
    )
    droits = sortie.split()[-1]
    assert int(droits, 8) & 0o007 == 0, message(
        en=(
            f"{recette['socket_admin']} is mode {droits}: any account on the "
            "machine can drive the proxy."
        ),
        fr=(
            f"{recette['socket_admin']} est en mode {droits} : n'importe quel "
            "compte de la machine peut piloter le proxy."
        ),
    )


def test_le_dossier_nomme_la_cause_et_la_distingue_du_symptome(
    edge, recette
) -> None:
    """Relu par un humain. Le test vérifie la présence et la séparation.

    CE QUE CE TEST NE FAIT PAS : juger le diagnostic. Un 503 n'est pas une
    cause, c'est ce que le proxy répond quand il n'a plus de serveur, et au
    moins trois des cinq familles le produisent. Le test demande donc que le
    dossier parle des deux, et c'est un humain qui dira si le lien est juste.
    """
    contenu = edge.run(f"cat {recette['dossier']} 2>/dev/null").stdout
    assert contenu.strip(), message(
        en=(
            f"{recette['dossier']} is missing or empty. The recipe asks for a "
            "dossier naming the cause and separating it from its symptom."
        ),
        fr=(
            f"{recette['dossier']} est absent ou vide. La recette demande un "
            "dossier qui nomme la cause et la sépare de son symptôme."
        ),
    )
    assert len(contenu) >= 400, message(
        en=f"{recette['dossier']} holds {len(contenu)} characters: too short to separate both.",
        fr=f"{recette['dossier']} porte {len(contenu)} caractères : trop court pour séparer les deux.",
    )

    minuscules = contenu.lower()
    familles = (
        "routage", "routing", "sonde", "probe", "check",
        "tls", "certificat", "certificate", "autorite", "autorité",
        "limite", "limit", "saturation", "file", "queue", "maxconn",
    )
    assert any(motif in minuscules for motif in familles), message(
        en=(
            f"{recette['dossier']} names no cause family. The five possible "
            "ones are routing, the health probe, backend TLS trust, a traffic "
            "limit and saturation."
        ),
        fr=(
            f"{recette['dossier']} ne nomme aucune famille de cause. Les cinq "
            "possibles sont le routage, la sonde de santé, la confiance TLS vers "
            "le backend, une limite de trafic et la saturation."
        ),
    )
    symptomes = ("502", "503", "504", "429", "404", "code", "statut", "status")
    assert any(motif in minuscules for motif in symptomes), message(
        en=(
            f"{recette['dossier']} does not mention the symptom you observed. "
            "The point of the dossier is to separate the two: the code is what "
            "you saw, the cause is what produced it, and the same code comes "
            "from several causes."
        ),
        fr=(
            f"{recette['dossier']} ne mentionne pas le symptôme observé. Tout "
            "l'intérêt du dossier est de séparer les deux : le code est ce qu'on "
            "a vu, la cause est ce qui l'a produit, et le même code vient de "
            "plusieurs causes."
        ),
    )
