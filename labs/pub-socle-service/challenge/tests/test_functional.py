"""Vérifie la fiche de service contre le système, jamais contre le texte d'un corrigé.

Seul le contenu de `recette` relève d'une relecture humaine : aucun test ne
prétend en juger la qualité.
"""

from __future__ import annotations

import json

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
FICHE = "/home/student/fiche-service.yaml"
APP = "pub-catalogue"
STOCK = "pub-stock"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def fiche(edge):
    fichier = edge.file(FICHE)
    assert fichier.exists, message(
        en=f"The service sheet {FICHE} does not exist.",
        fr=f"La fiche de service {FICHE} n'existe pas.",
    )
    try:
        contenu = yaml.safe_load(fichier.content_string)
    except yaml.YAMLError as erreur:
        pytest.fail(message(
            en=f"{FICHE} is not valid YAML: {erreur}",
            fr=f"{FICHE} n'est pas un YAML valide : {erreur}",
        ))
    assert isinstance(contenu, dict), message(
        en=f"{FICHE} must contain a YAML mapping.",
        fr=f"{FICHE} doit contenir un dictionnaire YAML.",
    )
    return contenu


def _propriete(edge, unite, nom):
    res = edge.run(f"systemctl show {unite} --property={nom} --value")
    return res.stdout.strip()


def _port_d_ecoute(edge, pid):
    res = edge.run(f"sudo ss -Hltnp | grep 'pid={pid},'")
    for ligne in res.stdout.splitlines():
        adresse = ligne.split()[3]
        return int(adresse.rsplit(":", 1)[1])
    return None


def _environnement(edge, unite):
    brut = _propriete(edge, unite, "Environment")
    return dict(item.split("=", 1) for item in brut.split() if "=" in item)


def _http(edge, port, chemin):
    res = edge.run(
        f"curl --max-time 5 --silent --output /tmp/pub-socle-corps "
        f"--write-out '%{{http_code}}' http://127.0.0.1:{port}{chemin}"
    )
    corps = edge.run("cat /tmp/pub-socle-corps").stdout
    return res.stdout.strip(), corps


def _port_app(edge):
    pid = _propriete(edge, APP, "MainPID")
    return _port_d_ecoute(edge, pid) if pid not in ("", "0") else None


def test_fiche_identifie_le_processus_reel(edge, fiche) -> None:
    pid = _propriete(edge, APP, "MainPID")
    utilisateur = edge.run(f"ps -o user= -p {pid}").stdout.strip()
    port = _port_d_ecoute(edge, pid)
    assert fiche.get("service") in {APP, f"{APP}.service"}, message(
        en=f"'service' must name the unit that serves the application, got {fiche.get('service')!r}.",
        fr=f"'service' doit nommer l'unité qui sert l'application, reçu {fiche.get('service')!r}.",
    )
    assert fiche.get("utilisateur") == utilisateur, message(
        en=f"'utilisateur' does not match the user of the running process ({utilisateur}).",
        fr=f"'utilisateur' ne correspond pas à l'utilisateur du processus en marche ({utilisateur}).",
    )
    assert fiche.get("ecoute") == port, message(
        en="'ecoute' does not match the port the process really listens on.",
        fr="'ecoute' ne correspond pas au port réellement écouté par le processus.",
    )


def test_fiche_identifie_la_dependance_reelle(edge, fiche) -> None:
    port_stock = int(_environnement(edge, APP)["STOCK_PORT"])
    utilisateur = _propriete(edge, STOCK, "User")
    dependances = fiche.get("dependances")
    assert isinstance(dependances, list) and dependances, message(
        en="'dependances' must list the dependency of the application.",
        fr="'dependances' doit lister la dépendance de l'application.",
    )
    attendu = {"nom": STOCK, "utilisateur": utilisateur, "port": port_stock}
    trouvees = [
        {"nom": str(d.get("nom", "")).removesuffix(".service"),
         "utilisateur": d.get("utilisateur"), "port": d.get("port")}
        for d in dependances if isinstance(d, dict)
    ]
    assert attendu in trouvees, message(
        en="No entry of 'dependances' matches the real dependency (unit, user and port).",
        fr="Aucune entrée de 'dependances' ne correspond à la vraie dépendance (unité, utilisateur, port).",
    )


def test_fonction_metier_retablie(edge) -> None:
    port = _port_app(edge)
    assert port, message(
        en="The application is not running.", fr="L'application n'est pas lancée."
    )
    code_accueil, _ = _http(edge, port, "/")
    code_api, corps = _http(edge, port, "/api/livres")
    reel = json.loads(edge.file("/opt/pub-socle/livres.json").content_string)
    assert code_accueil == "200" and code_api == "200", message(
        en=f"Home page HTTP {code_accueil}, /api/livres HTTP {code_api}: the business function is still down.",
        fr=f"Accueil HTTP {code_accueil}, /api/livres HTTP {code_api} : la fonction métier est toujours indisponible.",
    )
    assert json.loads(corps) == reel, message(
        en="/api/livres does not return the real list of books.",
        fr="/api/livres ne renvoie pas la vraie liste de livres.",
    )


def test_effet_de_l_arret_de_la_dependance(edge) -> None:
    port = _port_app(edge)
    assert port and _propriete(edge, STOCK, "ActiveState") == "active", message(
        en="The dependency must be running before measuring what its stop does.",
        fr="La dépendance doit tourner avant de mesurer l'effet de son arrêt.",
    )
    try:
        edge.run(f"sudo systemctl stop {STOCK}")
        accueil, _ = _http(edge, port, "/")
        sante, _ = _http(edge, port, "/health")
        api, _ = _http(edge, port, "/api/livres")
    finally:
        edge.run(f"sudo systemctl start {STOCK}")
    assert (accueil, sante, api) == ("200", "200", "503"), message(
        en=f"With the dependency stopped, expected (200, 200, 503), got {(accueil, sante, api)}.",
        fr=f"Dépendance arrêtée, attendu (200, 200, 503), obtenu {(accueil, sante, api)}.",
    )


def test_fiche_decrit_l_effet_du_redemarrage(edge, fiche) -> None:
    port = _port_app(edge)
    assert port, message(
        en="The application is not running.", fr="L'application n'est pas lancée."
    )
    _http(edge, port, "/")
    _, avant = _http(edge, port, "/api/etat")
    avant = json.loads(avant)
    edge.run(f"sudo systemctl restart {APP}")
    for _ in range(20):
        port = _port_app(edge)
        if port and _http(edge, port, "/health")[0] == "200":
            break
        edge.run("sleep 1")
    _, apres = _http(edge, port, "/api/etat")
    apres = json.loads(apres)
    conserve = sorted(k for k in avant if apres[k] >= avant[k])
    perdu = sorted(k for k in avant if apres[k] < avant[k])
    redemarrage = fiche.get("redemarrage") or {}
    assert sorted(redemarrage.get("conserve") or []) == conserve, message(
        en=f"'redemarrage.conserve' does not match what a restart keeps ({conserve}).",
        fr=f"'redemarrage.conserve' ne correspond pas à ce qu'un redémarrage conserve ({conserve}).",
    )
    assert sorted(redemarrage.get("perdu") or []) == perdu, message(
        en=f"'redemarrage.perdu' does not match what a restart loses ({perdu}).",
        fr=f"'redemarrage.perdu' ne correspond pas à ce qu'un redémarrage perd ({perdu}).",
    )
