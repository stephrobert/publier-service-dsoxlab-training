"""Vérifie l'exposition réelle du service, depuis le client et depuis l'hôte.

Les tests sondent eux-mêmes les trois ports avec un nonce aléatoire : seul
l'état observé compte, jamais le texte de la matrice de l'apprenant.
"""

from __future__ import annotations

import re
import secrets

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
FICHE = "/home/student/flux.yaml"
SERVICES = ("public", "backend", "admin")
POLITIQUE = {
    "public": {"client": "ouvert", "local": "ouvert"},
    "backend": {"client": "ferme", "local": "ouvert"},
    "admin": {"client": "ferme", "local": "ouvert"},
}


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def client():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def ports(edge):
    brut = edge.run("sudo cat /etc/pub-expo/ports.env").stdout
    trouves = {m.group(1).lower(): int(m.group(2)) for m in re.finditer(r"(\w+)=(\d+)", brut)}
    assert set(trouves) == set(SERVICES), message(
        en="The lab ports are missing.", fr="Les ports du lab sont introuvables."
    )
    return trouves


@pytest.fixture(scope="module")
def adresse(edge):
    iface = edge.run("ip -4 route show default | awk '{print $5; exit}'").stdout.strip()
    ip = edge.run(
        f"ip -4 -o addr show dev {iface} scope global | awk '{{print $4}}' | cut -d/ -f1 | head -1"
    ).stdout.strip()
    assert ip, message(en="No address found on edge.lab.", fr="Aucune adresse trouvée sur edge.lab.")
    return ip


def _sonder(hote, ip: str, port: int) -> tuple[str, str]:
    """Ouvert ou ferme, mesure sur la REPONSE et non sur son CORPS.

    La premiere version lisait `res.stdout` : un service qui repond sans corps
    etait classe « ferme » alors qu'il est joignable. Mesure du 2026-10-25, par
    contre-test : un serveur local rendant **204 No Content** passait pour un
    port ferme, et l'exercice declarait close une exposition bien ouverte.

    `%{http_code}` rend **000** quand la connexion n'aboutit pas, et le code
    HTTP des qu'un serveur repond, corps vide compris. C'est donc lui qui
    distingue les deux etats, jamais la longueur du corps.
    """
    nonce = secrets.token_hex(6)
    res = hote.run(
        f"curl -s -o /dev/null --max-time 3 -H 'X-Nonce: {nonce}' "
        f"-w '%{{http_code}}' http://{ip}:{port}/"
    )
    code = res.stdout.strip()
    return ("ferme" if code in ("", "000") else "ouvert"), nonce


def _observe(edge, client, ports, adresse) -> dict:
    vue = {}
    for nom in SERVICES:
        vue[nom] = {
            "client": _sonder(client, adresse, ports[nom])[0],
            "local": _sonder(edge, "127.0.0.1", ports[nom])[0],
        }
    return vue


def test_service_public_repond_et_le_contournement_est_ferme(client, ports, adresse) -> None:
    etat, nonce = _sonder(client, adresse, ports["public"])
    res = client.run(
        f"curl -s --max-time 3 -H 'X-Nonce: {nonce}' http://{adresse}:{ports['public']}/"
    ).stdout
    assert etat == "ouvert" and "pub-backend" in res and nonce in res, message(
        en="The public service must answer from the client with the backend's reply and the nonce.",
        fr="Le service public doit répondre depuis le client avec la réponse du backend et le nonce.",
    )
    assert _sonder(client, adresse, ports["backend"])[0] == "ferme", message(
        en="The public service works, but the backend is still reachable directly from the client.",
        fr="Le service public fonctionne, mais le backend reste joignable directement depuis le client.",
    )


@pytest.mark.parametrize("nom", ["backend", "admin"])
def test_chemin_direct_ferme_au_client_et_ouvert_en_local(edge, client, ports, adresse, nom) -> None:
    assert _sonder(client, adresse, ports[nom])[0] == "ferme", message(
        en=f"The {nom} port is still reachable from the client, bypassing the entry point.",
        fr=f"Le port {nom} est encore joignable depuis le client, en contournant le point d'entrée.",
    )
    assert _sonder(edge, "127.0.0.1", ports[nom])[0] == "ouvert", message(
        en=f"The {nom} service is closed to the client but must stay reachable from edge.lab itself.",
        fr=f"Le service {nom} est fermé au client mais doit rester joignable depuis edge.lab elle-même.",
    )


def test_matrice_conforme_a_la_politique_et_a_l_observation(edge, client, ports, adresse) -> None:
    fichier = edge.file(FICHE)
    assert fichier.exists, message(en=f"{FICHE} does not exist.", fr=f"{FICHE} n'existe pas.")
    try:
        flux = (yaml.safe_load(fichier.content_string) or {}).get("flux")
    except yaml.YAMLError as erreur:
        pytest.fail(message(en=f"{FICHE} is not valid YAML: {erreur}",
                            fr=f"{FICHE} n'est pas un YAML valide : {erreur}"))
    assert isinstance(flux, dict), message(
        en="'flux' must be a mapping.", fr="'flux' doit être un dictionnaire."
    )
    vue = _observe(edge, client, ports, adresse)
    for nom in SERVICES:
        ligne = flux.get(nom) or {}
        assert ligne.get("port") == ports[nom], message(
            en=f"'flux.{nom}.port' is wrong: the service listens on {ports[nom]}.",
            fr=f"'flux.{nom}.port' est faux : le service écoute sur {ports[nom]}.",
        )
        for point in ("client", "local"):
            assert ligne.get(point) == vue[nom][point] == POLITIQUE[nom][point], message(
                en=f"'flux.{nom}.{point}' must be '{POLITIQUE[nom][point]}' and match the observation ('{vue[nom][point]}').",
                fr=f"'flux.{nom}.{point}' doit valoir '{POLITIQUE[nom][point]}' et correspondre à l'observation ('{vue[nom][point]}').",
            )
