"""Verify that both entry points serve, that losing a process then a host
moves the service address without touching the client, that policy and
certificates stay consistent across the failover, and that the dossier says
what the failover does not protect.

CE QUE LE SETUP POSE : deux points d'entree complets, avec la MEME
configuration et le MEME certificat, et keepalived installe sans
configuration. L'adresse de service n'appartient a aucune des deux.

LA MESURE SE FAIT SANS TOUCHER AU CLIENT

La sonde interroge la meme adresse pendant toute la perte, et ne change
rien. C'est la condition de la mesure : une bascule qui demanderait une
action du client n'en serait pas une, et un test qui relancerait la sonde
sur l'autre adresse mesurerait sa propre intervention.

POURQUOI LA PERTE D'UN PROCESSUS EST LE CONTROLE LE PLUS INSTRUCTIF

Une bascule qui ne surveille que la machine ne voit pas un proxy mort sur
une machine vivante. L'adresse reste ou elle est, la haute disponibilite se
porte bien, et le service est a terre. C'est la panne la plus frequente de
cette famille, et la plus longue a diagnostiquer.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
PAIR = "edge2.lab"
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-ha/recette.txt"
MARQUE = "pub-haproxy-ha service"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def pair():
    return lab_host(PAIR)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


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
def recette(edge) -> dict:
    # Les adresses des deux points d'entree viennent de l'INVENTAIRE, pas de
    # la recette : elles derivent de la position de l'hote dans le meta.yml,
    # donc une valeur recopiee dans la recette se perime le jour ou le CIDR
    # ou l'ordre des hotes change, sans que rien ne le dise.
    #
    # La recette les porte quand meme, parce que l'apprenant en a besoin, et
    # le test verifie que les deux sources disent la meme chose. Un ecart ici
    # signale une recette perimee, et non un travail fautif.
    entrees = {"edge": lab_host_ip(CIBLE), "edge2": lab_host_ip(PAIR)}
    declarees = {}
    for ligne in _lignes(edge, "entree"):
        nom, adresse = ligne.split()
        declarees[nom] = adresse
    assert declarees == entrees, message(
        en=(
            f"The recipe announces the entry points at {declarees} while the "
            f"inventory places them at {entrees}. The recipe is stale: host "
            "addresses derive from their position in meta.yml."
        ),
        fr=(
            f"La recette annonce les points d'entrée en {declarees} alors que "
            f"l'inventaire les place en {entrees}. La recette est périmée : "
            "l'adresse d'un hôte dérive de sa position dans le meta.yml."
        ),
    )
    return {
        "nom_service": _valeur(edge, "nom_service"),
        "ip_flottante": _valeur(edge, "ip_flottante"),
        "entrees": entrees,
        "route_publique": _valeur(edge, "route_publique"),
        "route_privee": _valeur(edge, "route_privee"),
        "dossier": _valeur(edge, "dossier"),
    }


CA_CLIENT = "/usr/local/share/pub-haproxy-ha-ca.crt"


def _interroger(poste, recette, adresse: str, chemin: str):
    """Une requête STRICTE depuis le client, vers une adresse donnée."""
    nom = recette["nom_service"]
    statut = poste.run(
        f"curl -sS --cacert {CA_CLIENT} --resolve {nom}:443:{adresse} "
        f"-o /tmp/corps-ha -w '%{{http_code}}' --max-time 15 "
        f"https://{nom}{chemin}"
    ).stdout.strip()
    corps = poste.run("cat /tmp/corps-ha 2>/dev/null").stdout
    return statut, corps


def _empreinte(machine, recette) -> str:
    nom = recette["nom_service"]
    return machine.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
        f"2>/dev/null | openssl x509 -noout -fingerprint -sha256"
    ).stdout.strip()


def _porteur(edge, pair, recette) -> str:
    """Quelle machine porte l'adresse de service, en la lui demandant."""
    ip = recette["ip_flottante"]
    for nom, machine in (("edge", edge), ("edge2", pair)):
        sortie = machine.run(f"ip -o -4 addr show | grep -c ' {ip}/' ").stdout.strip()
        if sortie not in ("", "0"):
            return nom
    return ""


def _qui_repond(poste, recette) -> str:
    _statut, corps = _interroger(
        poste, recette, recette["ip_flottante"], recette["route_publique"]
    )
    for ligne in corps.splitlines():
        if ligne.startswith(MARQUE):
            return ligne.rsplit(" ", 1)[-1]
    return ""


def _mesures(poste, chemin: str) -> list[str]:
    return [
        ligne.strip()
        for ligne in poste.run(f"cat {chemin} 2>/dev/null").stdout.splitlines()
        if ligne.strip()
    ]



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

def test_les_deux_points_d_entree_servent_la_recette(poste, recette) -> None:
    """Chacun par son adresse propre, en TLS strict, avant toute bascule."""
    for nom, adresse in recette["entrees"].items():
        statut, corps = _interroger(
            poste, recette, adresse, recette["route_publique"]
        )
        assert statut == "200", message(
            en=(
                f"Entry point {nom} ({adresse}) answered {statut} on its own "
                f"address ({corps.strip()[:160]!r}). A pair whose member does "
                "not serve is not a pair."
            ),
            fr=(
                f"Le point d'entrée {nom} ({adresse}) a répondu {statut} sur son "
                f"adresse propre ({corps.strip()[:160]!r}). Une paire dont un "
                "membre ne sert pas n'est pas une paire."
            ),
        )
        assert f"{MARQUE} {nom}" in corps, message(
            en=f"{adresse} answers, but not from {nom} ({corps.strip()[:160]!r}).",
            fr=f"{adresse} répond, mais pas depuis {nom} ({corps.strip()[:160]!r}).",
        )

    statut, corps = _interroger(
        poste, recette, recette["ip_flottante"], recette["route_publique"]
    )
    assert statut == "200" and MARQUE in corps, message(
        en=(
            f"The service address {recette['ip_flottante']} answered {statut} "
            f"({corps.strip()[:160]!r}). It belongs to neither machine at rest: "
            "making it exist is the mission."
        ),
        fr=(
            f"L'adresse de service {recette['ip_flottante']} a répondu {statut} "
            f"({corps.strip()[:160]!r}). Elle n'appartient à aucune des deux "
            "machines au repos : la faire exister est la mission."
        ),
    )


def test_la_perte_d_un_processus_puis_d_un_hote_bascule(
    edge, pair, poste, recette
) -> None:
    """Les deux pertes, mesurées sans rien changer côté client."""
    porteur = _porteur(edge, pair, recette)
    assert porteur, message(
        en=(
            f"Neither machine carries {recette['ip_flottante']}. The service "
            "address must exist somewhere for a failover to be measurable."
        ),
        fr=(
            f"Aucune des deux machines ne porte {recette['ip_flottante']}. "
            "L'adresse de service doit exister quelque part pour qu'une bascule "
            "soit mesurable."
        ),
    )
    machines = {"edge": edge, "edge2": pair}
    autre = "edge2" if porteur == "edge" else "edge"

    # --- PERTE D'UN PROCESSUS -------------------------------------------
    sonde = "/tmp/sonde-ha.txt"
    poste.run(f"rm -f {sonde}")
    poste.run(
        f"nohup sonde-entree {recette['ip_flottante']} {recette['nom_service']} "
        f"60 {sonde} >/dev/null 2>&1 &"
    )
    time.sleep(5)
    machines[porteur].run("sudo systemctl stop haproxy")
    try:
        limite = time.monotonic() + 45
        bascule = ""
        while time.monotonic() < limite:
            if _qui_repond(poste, recette) == autre:
                bascule = autre
                break
            time.sleep(2)
        assert bascule == autre, message(
            en=(
                f"HAProxy was stopped on {porteur} and the service address is "
                f"still not served by {autre} after 45s. A failover that only "
                "watches the machine does not see a dead proxy on a live "
                "machine: the address stays where it is, high availability is "
                "doing fine, and the service is down."
            ),
            fr=(
                f"HAProxy a été arrêté sur {porteur} et l'adresse de service "
                f"n'est toujours pas servie par {autre} après 45 s. Une bascule "
                "qui ne surveille que la machine ne voit pas un proxy mort sur "
                "une machine vivante : l'adresse reste où elle est, la haute "
                "disponibilité se porte bien, et le service est à terre."
            ),
        )
    finally:
        machines[porteur].run("sudo systemctl start haproxy")

    mesures = [ligne for ligne in _mesures(poste, sonde) if ligne != "fin"]
    erreurs = [ligne for ligne in mesures if "erreur" in ligne]
    assert len(erreurs) <= 15, message(
        en=(
            f"{len(erreurs)} of {len(mesures)} probes failed during the process "
            f"loss ({erreurs[:4]}). The client changed nothing: what it saw is "
            "what a user would have seen."
        ),
        fr=(
            f"{len(erreurs)} sondes sur {len(mesures)} ont échoué pendant la "
            f"perte du processus ({erreurs[:4]}). Le client n'a rien changé : ce "
            "qu'il a vu est ce qu'un utilisateur aurait vu."
        ),
    )

    # --- PERTE D'UN HOTE ------------------------------------------------
    time.sleep(15)
    porteur = _porteur(edge, pair, recette)
    assert porteur, message(
        en="No machine carries the service address before the host loss.",
        fr="Aucune machine ne porte l'adresse de service avant la perte d'hôte.",
    )
    autre = "edge2" if porteur == "edge" else "edge"

    # Un redemarrage plutot qu'un arret : l'hote disparait vraiment, et il
    # revient de lui-meme. Un arret laisserait le lab dans un etat que seul
    # un humain peut defaire.
    machines[porteur].run(
        "nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &"
    )
    time.sleep(8)

    limite = time.monotonic() + 90
    repris = ""
    while time.monotonic() < limite:
        if _qui_repond(poste, recette) == autre:
            repris = autre
            break
        time.sleep(3)
    assert repris == autre, message(
        en=(
            f"The host {porteur} went away and {autre} did not take over the "
            "service address within 90s. The surviving entry point must claim "
            "it by itself, without anything on the client changing."
        ),
        fr=(
            f"L'hôte {porteur} a disparu et {autre} n'a pas repris l'adresse de "
            "service dans les 90 s. Le point d'entrée survivant doit la "
            "réclamer de lui-même, sans que rien ne change côté client."
        ),
    )

    # On attend le retour de la machine : la laisser absente ferait echouer
    # les controles suivants pour une raison qui n'est pas la leur.
    revenue = _attendre_retour(machines[porteur], 180)
    assert revenue, message(
        en=f"{porteur} did not come back online within 180s after its reboot.",
        fr=f"{porteur} n'est pas revenue en ligne dans les 180 s après son redémarrage.",
    )
    time.sleep(20)


def test_la_politique_et_les_certificats_restent_coherents(
    edge, pair, poste, recette
) -> None:
    """CRITIQUE : même empreinte des deux côtés, et le refus tient après la bascule."""
    empreintes = {"edge": _empreinte(edge, recette), "edge2": _empreinte(pair, recette)}
    for nom, empreinte in empreintes.items():
        assert "Fingerprint" in empreinte, message(
            en=f"No certificate read on {nom} ({empreinte[:120]!r}).",
            fr=f"Aucun certificat lu sur {nom} ({empreinte[:120]!r}).",
        )
    assert empreintes["edge"] == empreintes["edge2"], message(
        en=(
            f"The two entry points present different certificates: {empreintes}. "
            "A client that verifies strictly would then see a different service "
            "depending on which one answers, which is exactly what a failover "
            "must prevent."
        ),
        fr=(
            f"Les deux points d'entrée présentent des certificats différents : "
            f"{empreintes}. Un client qui vérifie strictement verrait alors un "
            "service différent selon celui qui répond, ce qu'une bascule doit "
            "justement empêcher."
        ),
    )

    statut, corps = _interroger(
        poste, recette, recette["ip_flottante"], recette["route_publique"]
    )
    assert statut == "200" and MARQUE in corps, message(
        en=f"After the failover, the public route answers {statut}.",
        fr=f"Après la bascule, la route publique répond {statut}.",
    )

    statut, _corps = _interroger(
        poste, recette, recette["ip_flottante"], recette["route_privee"]
    )
    assert statut == "403", message(
        en=(
            f"After the failover, the private route answers {statut} from the "
            "client, expected 403. A policy that does not follow the service is "
            "an opening that does not know itself: it appears the day of an "
            "incident, on the machine nobody was looking at."
        ),
        fr=(
            f"Après la bascule, la route privée répond {statut} depuis le "
            "client, on attend 403. Une politique qui ne suit pas le service est "
            "une ouverture qui s'ignore : elle apparaît le jour d'un incident, "
            "sur la machine que personne ne regardait."
        ),
    )

    for nom, adresse in recette["entrees"].items():
        statut, _corps = _interroger(
            poste, recette, adresse, recette["route_privee"]
        )
        assert statut == "403", message(
            en=f"Entry point {nom} answers {statut} on the private route.",
            fr=f"Le point d'entrée {nom} répond {statut} sur la route privée.",
        )


def test_le_dossier_decrit_les_limites(edge, recette) -> None:
    """Relu par un humain. Trois sujets, dont aucun ne se lit dans la configuration."""
    contenu = edge.run(f"cat {recette['dossier']} 2>/dev/null").stdout
    assert len(contenu) >= 600, message(
        en=(
            f"{recette['dossier']} is missing, empty or too short "
            f"({len(contenu)} characters). Three subjects are expected."
        ),
        fr=(
            f"{recette['dossier']} est absent, vide ou trop court "
            f"({len(contenu)} caractères). Trois sujets sont attendus."
        ),
    )
    minuscules = contenu.lower()
    sujets = (
        (
            "la partition réseau et le double maître qu'elle produit",
            ("split", "partition", "double maitre", "double maître", "deux maitres"),
        ),
        (
            "l'état qui n'est pas répliqué",
            ("replic", "réplic", "etat", "état", "session"),
        ),
        (
            "ce que la bascule ne couvre pas",
            ("ne protege", "ne protège", "ne couvre", "limite"),
        ),
    )
    for sujet, motifs in sujets:
        assert any(motif in minuscules for motif in motifs), message(
            en=(
                f"{recette['dossier']} does not cover {sujet}. These three are "
                "not readable in the configuration, and they are what separates "
                "a failover that was deployed from one whose reach is known."
            ),
            fr=(
                f"{recette['dossier']} ne traite pas {sujet}. Ces trois sujets ne "
                "se lisent pas dans la configuration, et ils font la différence "
                "entre une bascule déployée et une bascule dont on connaît la "
                "portée."
            ),
        )
