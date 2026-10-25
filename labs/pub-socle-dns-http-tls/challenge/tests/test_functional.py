"""Vérifie que le SNI, le Host et le DNS sont trois décisions distinctes.

Les tests sondent eux-mêmes le routeur depuis `poste.lab`, avec l'autorité de
test fournie et sans jamais désactiver la vérification de nom (sauf pour la
sonde du nom inconnu, qui vérifie volontairement la chaîne seule : c'est la
méthode qui permet d'observer ce que sert réellement le routeur à un nom
qu'il ne reconnaît pas). Rien ici ne fait confiance au texte de la fiche de
l'apprenant sans le confronter à ce qui est réellement observé.
"""

from __future__ import annotations

import json

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
FICHE = "/home/student/diagnostic.yaml"
ETAT = "/var/lib/pub-dht/etat.json"
CA = "/home/student/ca.pem"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def client():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


@pytest.fixture(scope="module")
def fiche(edge):
    fichier = edge.file(FICHE)
    assert fichier.exists, message(
        en=f"{FICHE} does not exist on edge.lab.",
        fr=f"{FICHE} n'existe pas sur edge.lab.",
    )
    try:
        contenu = yaml.safe_load(fichier.content_string)
    except yaml.YAMLError as erreur:
        pytest.fail(
            message(
                en=f"{FICHE} is not valid YAML: {erreur}",
                fr=f"{FICHE} n'est pas un YAML valide : {erreur}",
            )
        )
    assert isinstance(contenu, dict), message(
        en=f"{FICHE} must contain a YAML mapping.",
        fr=f"{FICHE} doit contenir un dictionnaire YAML.",
    )
    return contenu


def _curl(client, resolu: str, ip: str, hote_envoye: str, cacert: str = CA) -> tuple[int, str]:
    """GET en TLS depuis poste.lab, SNI = `resolu`, Host = `hote_envoye`."""
    cmd = (
        f"curl -s --max-time 5 --cacert {cacert} --resolve {resolu}:443:{ip} "
        f"-H 'Host: {hote_envoye}' https://{resolu}/"
    )
    res = client.run(cmd)
    return res.rc, res.stdout


def test_dns_resolution_normale_distincte_de_forcee(client, etat, fiche) -> None:
    assert fiche.get("resolveur") == etat["resolveur"], message(
        en=f"'resolveur' is wrong: poste.lab queries {etat['resolveur']} for dht.test.",
        fr=f"'resolveur' est faux : poste.lab interroge {etat['resolveur']} pour dht.test.",
    )

    for nom in ("boutique.dht.test", "compte.dht.test"):
        reponse = client.run(f"dig +short {nom} A").stdout.strip()
        assert reponse == etat["edge_ip"], message(
            en=f"Normal DNS resolution of {nom} does not return edge.lab's address.",
            fr=f"La résolution DNS normale de {nom} ne renvoie pas l'adresse de edge.lab.",
        )

    nom_inconnu = etat["nom_inconnu"]
    reponse_inconnu = client.run(f"dig +short {nom_inconnu} A").stdout.strip()
    assert reponse_inconnu == "", message(
        en=f"{nom_inconnu} was never registered in any zone: normal DNS must not answer for it.",
        fr=f"{nom_inconnu} n'a jamais été enregistré dans aucune zone : le DNS normal ne doit pas répondre pour lui.",
    )
    assert fiche.get("nom_inconnu_resout") is False, message(
        en="'nom_inconnu_resout' must be false: normal DNS resolution does not answer for the unknown name.",
        fr="'nom_inconnu_resout' doit valoir false : la résolution DNS normale ne répond pas pour le nom inconnu.",
    )


def test_sni_choisit_le_certificat_chaine_et_san_verifies(client, etat, fiche) -> None:
    assert fiche.get("sni_boutique") == "boutique.dht.test", message(
        en="'sni_boutique' must be 'boutique.dht.test'.",
        fr="'sni_boutique' doit valoir 'boutique.dht.test'.",
    )
    assert fiche.get("sni_compte") == "compte.dht.test", message(
        en="'sni_compte' must be 'compte.dht.test'.",
        fr="'sni_compte' doit valoir 'compte.dht.test'.",
    )

    ip = etat["edge_ip"]
    for nom, jeton in (
        ("boutique.dht.test", etat["jeton_boutique"]),
        ("compte.dht.test", etat["jeton_compte"]),
    ):
        rc, corps = _curl(client, nom, ip, nom)
        assert rc == 0, message(
            en=f"TLS to {nom} failed (rc={rc}): the chain or the SAN did not verify against the given CA.",
            fr=f"Le TLS vers {nom} a échoué (rc={rc}) : la chaîne ou le SAN ne se vérifient pas avec la CA fournie.",
        )
        attendu = f"{nom.split('.')[0]}-{jeton}"
        assert attendu in corps, message(
            en=f"Connecting to {nom} with its own SNI and Host did not reach its own application.",
            fr=f"Se connecter à {nom} avec son propre SNI et son propre Host n'a pas atteint sa propre application.",
        )


def test_host_decide_le_routage_pas_le_sni(client, etat, fiche) -> None:
    assert fiche.get("host_decide_routage") is True, message(
        en="'host_decide_routage' must be true: the HTTP Host header decides which application answers.",
        fr="'host_decide_routage' doit valoir true : c'est l'en-tête HTTP Host qui décide quelle application répond.",
    )
    assert fiche.get("application_si_sni_boutique_host_compte") == "compte", message(
        en="'application_si_sni_boutique_host_compte' must be 'compte'.",
        fr="'application_si_sni_boutique_host_compte' doit valoir 'compte'.",
    )

    ip = etat["edge_ip"]
    rc, corps = _curl(client, "boutique.dht.test", ip, "compte.dht.test")
    assert rc == 0, message(
        en=f"TLS to boutique.dht.test with Host: compte.dht.test failed (rc={rc}).",
        fr=f"Le TLS vers boutique.dht.test avec Host: compte.dht.test a échoué (rc={rc}).",
    )
    attendu = f"compte-{etat['jeton_compte']}"
    assert attendu in corps, message(
        en=(
            "With SNI=boutique.dht.test (a valid, trusted certificate) and "
            "Host: compte.dht.test, the 'compte' application must answer: "
            "the Host header decides the route, not the certificate used."
        ),
        fr=(
            "Avec SNI=boutique.dht.test (un certificat valide et vérifié) et "
            "Host: compte.dht.test, c'est l'application 'compte' qui doit "
            "répondre : l'en-tête Host décide la route, pas le certificat "
            "utilisé."
        ),
    )


def test_nom_inconnu_refuse_par_aucune_application_par_accident(client, etat, fiche) -> None:
    """Point critique : un nom jamais enregistré ne doit atteindre aucune
    application, même en acceptant volontairement un certificat qui ne porte
    pas son nom (c'est la méthode qui permet d'observer le repli)."""
    assert fiche.get("nom_inconnu_doit_etre_refuse") is True, message(
        en="'nom_inconnu_doit_etre_refuse' must be true.",
        fr="'nom_inconnu_doit_etre_refuse' doit valoir true.",
    )

    ip = etat["edge_ip"]
    nom_inconnu = etat["nom_inconnu"]
    requete = f"printf 'GET / HTTP/1.0\\r\\nHost: {nom_inconnu}\\r\\n\\r\\n'"
    sonde = (
        f"{requete} | timeout 5 openssl s_client -quiet -connect {ip}:443 "
        f"-servername {nom_inconnu} -CAfile {CA} 2>&1 || true"
    )
    sortie = client.run(sonde).stdout

    for jeton in (etat["jeton_boutique"], etat["jeton_compte"]):
        assert jeton not in sortie, message(
            en=(
                f"The unknown name {nom_inconnu} reached an application by "
                "accident (its response leaked through). Add an explicit "
                "refusal in /etc/pub-dht/routes.yaml for names it does not "
                "recognise."
            ),
            fr=(
                f"Le nom inconnu {nom_inconnu} a atteint une application par "
                "accident (sa réponse a fuité). Ajoutez un refus explicite "
                "dans /etc/pub-dht/routes.yaml pour les noms qu'il ne "
                "reconnaît pas."
            ),
        )
