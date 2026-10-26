"""Vérifie le dossier d'architecture, la preuve de fonctionnement, le
diagnostic/réparation de l'incident et la restauration du lab
pub-epreuve-socle.

Un seul fait secret commande l'incident : la couche réellement cassée,
tirée au sort par `fixtures/prepare.sh` et conservée hors de portée de
l'apprenant dans `/root/.pub-eps-secret.yaml`. Le diagnostic écrit est
comparé à ce secret, jamais à un texte libre jugé au jugé.

Chaque test qui dépend d'un état durable le lit depuis `edge.lab` (où
tourne le banc) et observe depuis `poste.lab` (le client indépendant)
quand le point de vue du client est ce qui compte réellement.
"""

from __future__ import annotations

import json
import secrets

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
NOM = "epreuve.test"
DOSSIER = "/home/student/dossier.md"
INCIDENT_YAML = "/home/student/incident.yaml"
RESTAURER = "/home/student/restaurer.sh"
COUCHES = {"dns", "transport", "tls", "route", "backend"}


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def etat(edge):
    return yaml.safe_load(edge.run("sudo cat /var/lib/pub-eps/etat.json").stdout)


@pytest.fixture(scope="module")
def secret(edge):
    return yaml.safe_load(edge.run("sudo cat /root/.pub-eps-secret.yaml").stdout)


def _requete_https(
    poste, edge_ip: str, chemin: str, cacert: str = "/home/student/ca.pem"
) -> tuple[int, str]:
    option_ca = f"--cacert {cacert}" if cacert else ""
    res = poste.run(
        f"curl -s -o /dev/stdout -w '\\n%{{http_code}}' --max-time 5 "
        f"{option_ca} --resolve {NOM}:443:{edge_ip} https://{NOM}{chemin}"
    )
    sortie = res.stdout.rsplit("\n", 1)
    corps = sortie[0] if len(sortie) == 2 else ""
    code = int(sortie[-1]) if sortie[-1].strip().isdigit() else 0
    return code, corps


def test_besoin_dossier_architecture(edge) -> None:
    """Contrôle de PRÉSENCE, et qui le dit : la pertinence relève de la relecture.

    CE QUE CE TEST NE FAIT PLUS, ET POURQUOI

    Il exigeait 200 caractères et la présence de quelques mots attendus
    (« tls », « certificat », « responsab »). Contre-test du 2026-10-25 : un
    texte incohérent dépassant 200 caractères et saupoudré de ces mots-là
    validait l'épreuve. Le contrôle ne mesurait donc pas le dossier, il
    mesurait sa longueur et son vocabulaire, et surtout il transformait une
    relecture humaine ABSENTE en épreuve réussie.

    Un seuil de longueur et une liste de mots ne jugent pas un document.
    Plutôt que de faire semblant, ce test se borne à ce qu'une machine peut
    honnêtement affirmer : le dossier existe, il n'est pas vide, et il nomme
    le service qu'il documente. Savoir s'il couvre réellement les noms, les
    flux, les identités et les responsabilités est déclaré NON NOTÉ ici, et
    relève de la relecture, ce que le scénario annonce à l'apprenant.

    Le reste de l'épreuve, lui, se note : les trois tests qui suivent
    comparent des faits à l'état réel de la machine, jamais à un texte.
    """
    res = edge.run(f"cat {DOSSIER}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{DOSSIER} does not exist or is empty: the architecture dossier "
        f"must be written down, not kept in your head. Its content is read "
        f"by a human reviewer and is not graded here.",
        fr=f"{DOSSIER} n'existe pas ou est vide : le dossier d'architecture "
        f"doit être écrit, pas resté dans votre tête. Son contenu est lu par "
        f"un relecteur humain et n'est pas noté ici.",
    )
    assert NOM in res.stdout.lower(), message(
        en=f"{DOSSIER} never names the service it documents ({NOM}). This is "
        f"the only thing about the dossier a machine can check; everything "
        f"else is left to the human review the scenario announces.",
        fr=f"{DOSSIER} ne nomme jamais le service qu'il documente ({NOM}). "
        f"C'est la seule chose qu'une machine puisse contrôler du dossier ; "
        f"le reste est laissé à la relecture humaine que le scénario annonce.",
    )


def test_preuve_service_independant(poste, edge, etat) -> None:
    """Propriété critique : un client indépendant, avec une donnée qu'il
    n'a pas choisie à l'avance, obtient la bonne réponse sous vérification
    TLS stricte, et cette vérification n'est jamais contournée.
    """
    edge_ip = etat["edge_ip"]
    valeur_attendue = json.loads(
        edge.run("sudo cat /var/lib/pub-eps/donnees.json").stdout
    )["valeur"]
    nonce = secrets.token_hex(8)

    code, corps = _requete_https(poste, edge_ip, f"/?nonce={nonce}")
    assert code == 200, message(
        en=f"https://{NOM}/?nonce=... returns {code}, not 200.",
        fr=f"https://{NOM}/?nonce=... répond {code}, pas 200.",
    )
    reponse = json.loads(corps)
    assert reponse.get("nonce") == nonce, message(
        en="The response does not echo back the nonce chosen for this run: "
        "it may be cached or faked rather than really served.",
        fr="La réponse ne renvoie pas le nonce choisi pour cet essai : elle "
        "pourrait être mise en cache ou simulée plutôt que réellement servie.",
    )
    assert reponse.get("valeur") == valeur_attendue, message(
        en=f"The response carries valeur={reponse.get('valeur')!r}, not the "
        f"actual business value {valeur_attendue!r}.",
        fr=f"La réponse porte valeur={reponse.get('valeur')!r}, pas la vraie "
        f"valeur métier {valeur_attendue!r}.",
    )

    code_admin, _ = _requete_https(poste, edge_ip, "/admin")
    assert code_admin == 403, message(
        en=f"https://{NOM}/admin must be refused (403), got {code_admin}.",
        fr=f"https://{NOM}/admin doit être refusée (403), obtenu {code_admin}.",
    )

    sans_autorite = poste.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"--resolve {NOM}:443:{edge_ip} https://{NOM}/ 2>&1"
    )
    assert "200" not in sans_autorite.stdout, message(
        en="The request succeeds even without the test authority in the "
        "trust store: TLS validation is not actually strict.",
        fr="La requête aboutit même sans l'autorité de test dans le magasin "
        "de confiance : la vérification TLS n'est pas réellement stricte.",
    )


def test_incident_diagnostic_et_reparation(edge, poste, etat, secret) -> None:
    """Propriété critique : la couche réellement cassée est nommée
    précisément (un champ structuré comparé au secret, pas une recherche
    de mots dans un texte libre), et le service répond de nouveau,
    plusieurs fois de suite.
    """
    res = edge.run(f"cat {INCIDENT_YAML}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{INCIDENT_YAML} does not exist or is empty.",
        fr=f"{INCIDENT_YAML} n'existe pas ou est vide.",
    )
    diagnostic = yaml.safe_load(res.stdout) or {}
    couche = str(diagnostic.get("couche", "")).strip().lower()
    composant = str(diagnostic.get("composant", "")).strip().lower()
    explication = str(diagnostic.get("explication", "")).strip().lower()

    assert couche in COUCHES, message(
        en=f"{INCIDENT_YAML}'s 'couche' field must be one of {sorted(COUCHES)}, "
        f"got {couche!r}.",
        fr=f"Le champ 'couche' de {INCIDENT_YAML} doit valoir l'une de "
        f"{sorted(COUCHES)}, pas {couche!r}.",
    )
    assert couche == secret["incident"], message(
        en=f"{INCIDENT_YAML} names layer {couche!r}, but the actual incident "
        f"is on a different layer.",
        fr=f"{INCIDENT_YAML} nomme la couche {couche!r}, mais l'incident réel "
        f"est sur une autre couche.",
    )
    # CE QUI SE NOTE EST LE CHAMP STRUCTURE, PAS LA PROSE.
    #
    # La version precedente cherchait le mot-cle dans `composant` ET
    # `explication` reunis. Deux consequences, toutes deux mauvaises : le
    # champ structure pouvait rester VIDE pendant que de la prose libre
    # emportait le point, et un apprenant qui expliquait proprement ce qu'il
    # avait ECARTE se faisait recaler par le controle « tout citer a la fois
    # n'est pas un diagnostic », alors qu'enoncer ses hypotheses rejetees est
    # precisement ce qu'on attend d'un diagnostic.
    #
    # `explication` reste demandee par le scenario et lue par un relecteur :
    # elle n'est simplement pas notee ici.
    assert secret["mot_cle"] in composant, message(
        en=f"{INCIDENT_YAML}'s 'composant' field never names the actual "
        f"faulty component. Name it in that field: the free-text "
        f"'explication' is read by a human reviewer and is not graded here.",
        fr=f"Le champ 'composant' de {INCIDENT_YAML} ne nomme jamais le "
        f"composant réellement fautif. Nommez-le dans ce champ : le texte "
        f"libre 'explication' est lu par un relecteur humain et n'est pas "
        f"noté ici.",
    )
    for autre in secret["mots_cle_autres"]:
        assert autre not in composant, message(
            en=f"{INCIDENT_YAML}'s 'composant' field also names an unrelated "
            f"layer ({autre!r}): naming every layer at once is not a "
            f"diagnosis. Ruled-out hypotheses belong in 'explication'.",
            fr=f"Le champ 'composant' de {INCIDENT_YAML} nomme aussi une "
            f"couche sans rapport ({autre!r}) : tout citer à la fois n'est "
            f"pas un diagnostic. Les hypothèses écartées ont leur place dans "
            f"'explication'.",
        )

    # PRESENCE, pas contenu : le scenario demande une explication ecrite, et
    # on verifie qu'elle existe. Ce qu'elle VAUT est affaire de relecture, et
    # ce test ne pretend pas en juger.
    assert explication, message(
        en=f"{INCIDENT_YAML} carries no 'explication'. Write how you reached "
        f"the diagnosis: it is read by a human reviewer, and its content is "
        f"not graded here, but its absence is.",
        fr=f"{INCIDENT_YAML} ne porte aucune 'explication'. Écrivez comment "
        f"vous êtes arrivé au diagnostic : elle est lue par un relecteur "
        f"humain, son contenu n'est pas noté ici, mais son absence l'est.",
    )

    edge_ip = etat["edge_ip"]
    for essai in range(3):
        code, _ = _requete_https(poste, edge_ip, "/")
        assert code == 200, message(
            en=f"Attempt {essai + 1}/3: https://{NOM}/ returns {code}, not "
            f"200, after the repair.",
            fr=f"Essai {essai + 1}/3 : https://{NOM}/ répond {code}, pas 200, "
            f"après la correction.",
        )


def test_reprise_restauration_configuration_donnees_confiance(
    edge, poste, etat
) -> None:
    """Propriété critique : exécuter la restauration depuis la sauvegarde
    déjà en place et prouver qu'elle est digne de confiance, pas
    seulement qu'elle s'exécute : la bonne configuration, les bonnes
    données, et une chaîne TLS qui valide toujours strictement.
    """
    edge_ip = etat["edge_ip"]
    valeur_sauvegarde = json.loads(
        edge.run("sudo cat /var/backups/pub-eps/donnees.json.bak").stdout
    )["valeur"]
    port_sauvegarde = yaml.safe_load(
        edge.run("sudo cat /var/backups/pub-eps/route.yaml.bak").stdout
    )["port_backend"]

    presence_script = edge.run(f"test -f {RESTAURER}")
    assert presence_script.rc == 0, message(
        en=f"{RESTAURER} does not exist: there is no restore procedure to "
        f"run.",
        fr=f"{RESTAURER} n'existe pas : il n'y a pas de procédure de "
        f"restauration à exécuter.",
    )

    edge.run(
        "sudo rm -f /etc/pub-eps/route.yaml /var/lib/pub-eps/donnees.json"
    )

    resultat = edge.run(f"sudo bash {RESTAURER}")
    assert resultat.rc == 0, message(
        en=f"{RESTAURER} exits with status {resultat.rc}: {resultat.stderr}",
        fr=f"{RESTAURER} se termine avec le statut {resultat.rc} : "
        f"{resultat.stderr}",
    )

    config = yaml.safe_load(
        edge.run("sudo cat /etc/pub-eps/route.yaml").stdout
    )
    assert config and config.get("port_backend") == port_sauvegarde, message(
        en=f"After restore, /etc/pub-eps/route.yaml's port_backend is "
        f"{config.get('port_backend') if config else None!r}, not the backed "
        f"up {port_sauvegarde!r}.",
        fr=f"Après restauration, port_backend de /etc/pub-eps/route.yaml vaut "
        f"{config.get('port_backend') if config else None!r}, pas la valeur "
        f"sauvegardée {port_sauvegarde!r}.",
    )

    code, corps = _requete_https(poste, edge_ip, "/")
    assert code == 200, message(
        en=f"After restore, https://{NOM}/ returns {code}, not 200: the "
        f"configuration restore did not bring the service back.",
        fr=f"Après restauration, https://{NOM}/ répond {code}, pas 200 : la "
        f"restauration de configuration n'a pas relevé le service.",
    )
    reponse = json.loads(corps)
    assert reponse.get("valeur") == valeur_sauvegarde, message(
        en=f"After restore, the service answers valeur="
        f"{reponse.get('valeur')!r}, not the backed up {valeur_sauvegarde!r}: "
        f"the data restore did not actually use the backup.",
        fr=f"Après restauration, le service répond valeur="
        f"{reponse.get('valeur')!r}, pas la valeur sauvegardée "
        f"{valeur_sauvegarde!r} : la restauration des données n'a pas "
        f"réellement utilisé la sauvegarde.",
    )

    code_admin, _ = _requete_https(poste, edge_ip, "/admin")
    assert code_admin == 403, message(
        en=f"After restore, https://{NOM}/admin must still be refused "
        f"(403), got {code_admin}.",
        fr=f"Après restauration, https://{NOM}/admin doit toujours être "
        f"refusée (403), obtenu {code_admin}.",
    )

    sans_autorite = poste.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"--resolve {NOM}:443:{edge_ip} https://{NOM}/ 2>&1"
    )
    assert "200" not in sans_autorite.stdout, message(
        en="After restore, the request succeeds even without the test "
        "authority in the trust store: trust was not actually restored "
        "intact.",
        fr="Après restauration, la requête aboutit même sans l'autorité de "
        "test dans le magasin de confiance : la confiance n'a pas été "
        "réellement restaurée intacte.",
    )
