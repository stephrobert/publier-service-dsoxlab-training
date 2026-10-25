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
    """Revue humaine assistée par des observations : ce contrôle ne juge
    pas la pertinence du dossier (affaire de relecture humaine), il
    vérifie seulement que l'apprenant a bien produit un dossier
    substantiel qui couvre les quatre catégories attendues : les noms, les
    flux, les identités et les responsabilités.
    """
    res = edge.run(f"cat {DOSSIER}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{DOSSIER} does not exist or is empty: the architecture dossier "
        f"must be written down, not kept in your head.",
        fr=f"{DOSSIER} n'existe pas ou est vide : le dossier d'architecture "
        f"doit être écrit, pas resté dans votre tête.",
    )
    contenu = res.stdout
    bas = contenu.lower()
    assert len(contenu.strip()) >= 200, message(
        en=f"{DOSSIER} is too short to cover names, flows, identities and "
        f"responsibilities.",
        fr=f"{DOSSIER} est trop court pour couvrir noms, flux, identités et "
        f"responsabilités.",
    )
    assert NOM in bas, message(
        en=f"{DOSSIER} never names the service it documents ({NOM}).",
        fr=f"{DOSSIER} ne nomme jamais le service qu'il documente ({NOM}).",
    )
    a_flux = any(mot in bas for mot in ("443", "tls", "flux"))
    a_identite = any(
        mot in bas for mot in ("autorite", "autorité", "certificat", "ca ")
    )
    a_responsabilite = any(
        mot in bas for mot in ("responsab", "responsib")
    )
    assert a_flux and a_identite and a_responsabilite, message(
        en=f"{DOSSIER} must cover the TLS flow, the certificate authority "
        f"identity, and who is responsible for what.",
        fr=f"{DOSSIER} doit couvrir le flux TLS, l'identité de l'autorité de "
        f"certification, et les responsabilités de chacun.",
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
    composant_et_explication = f"{composant} {explication}"
    assert secret["mot_cle"] in composant_et_explication, message(
        en=f"{INCIDENT_YAML} never names the actual faulty component, nor "
        f"explains the incident from what was really observed.",
        fr=f"{INCIDENT_YAML} ne nomme jamais le composant réellement fautif, "
        f"ni n'explique l'incident à partir de ce qui a été réellement "
        f"observé.",
    )
    for autre in secret["mots_cle_autres"]:
        assert autre not in composant_et_explication, message(
            en=f"{INCIDENT_YAML} also names an unrelated layer ({autre!r}): "
            f"naming every layer at once is not a diagnosis.",
            fr=f"{INCIDENT_YAML} nomme aussi une couche sans rapport "
            f"({autre!r}) : tout citer à la fois n'est pas un diagnostic.",
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
