"""Vérifie la recette, la restauration, le retour en arrière et la grille de
limites du lab pub-socle-mise-en-service.

La recette s'exécute depuis `poste.lab`, un client indépendant d'`edge.lab` :
c'est la seule façon d'éprouver DNS, TLS et HTTP comme un vrai client les
rencontre, pas comme l'opérateur qui a posé le service les voit depuis
l'intérieur.

Chaque test qui modifie l'état actif le restaure en fin de test (sauvegarde
interne distincte de celle laissée à l'apprenant), pour que la suite reste
rejouable dans les deux sens par le validateur quel que soit l'ordre.
"""

from __future__ import annotations

import json
import time

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
NOM = "service.mes.test"
CONFIG = "/etc/pub-mes/route.yaml"
STOCK = "/var/lib/pub-mes/stock.json"
PURGE = "/var/lib/pub-mes/purge"
RECETTE = "/home/student/recette.yaml"
RESTAURER = "/home/student/restaurer.sh"
REVENIR = "/home/student/revenir-origine.sh"
LIMITES = "/home/student/limites.yaml"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run("sudo cat /var/lib/pub-mes/etat.json").stdout)


def _requete_https(poste, edge_ip: str, chemin: str) -> tuple[int, str]:
    res = poste.run(
        f"curl -s -o /dev/stdout -w '\\n%{{http_code}}' --max-time 5 "
        f"--cacert /home/student/ca.pem --resolve {NOM}:443:{edge_ip} "
        f"https://{NOM}{chemin}"
    )
    sortie = res.stdout.rsplit("\n", 1)
    corps = sortie[0] if len(sortie) == 2 else ""
    code = int(sortie[-1]) if sortie[-1].strip().isdigit() else 0
    return code, corps


def _attendre_code(poste, edge_ip: str, chemin: str, code_attendu: int, limite_s: float) -> int:
    limite = time.monotonic() + limite_s
    dernier = 0
    while time.monotonic() < limite:
        dernier, _ = _requete_https(poste, edge_ip, chemin)
        if dernier == code_attendu:
            return dernier
        time.sleep(1)
    return dernier


def test_recette_dns_tls_http_refus(edge, poste, etat) -> None:
    edge_ip = etat["edge_ip"]

    # DNS : résolution réelle via le résolveur configuré pour poste.lab, pas
    # un contournement par --resolve ou /etc/hosts.
    dig = poste.run(f"dig +short {NOM} A").stdout.strip().splitlines()
    assert edge_ip in dig, message(
        en=f"'dig {NOM} A' from poste.lab does not return {edge_ip}: got {dig}. "
        f"The DNS check must use the real resolver, never a bypass.",
        fr=f"'dig {NOM} A' depuis poste.lab ne retourne pas {edge_ip} : obtenu "
        f"{dig}. Le contrôle DNS doit passer par le vrai résolveur, jamais un "
        f"contournement.",
    )

    # TLS + HTTP : la route métier doit répondre, avec la chaîne vérifiée par
    # l'autorité du lab (jamais -k).
    code, corps = _requete_https(poste, edge_ip, "/catalogue")
    assert code == 200, message(
        en=f"GET /catalogue over TLS from poste.lab returns {code}, not 200.",
        fr=f"GET /catalogue en TLS depuis poste.lab retourne {code}, pas 200.",
    )
    assert "stock" in (json.loads(corps) if corps else {}), message(
        en="The /catalogue response has no 'stock' field.",
        fr="La réponse de /catalogue n'a pas de champ 'stock'.",
    )

    # Refus : la route interne de gestion ne doit jamais être exposée.
    code_interne, _ = _requete_https(poste, edge_ip, "/interne/compte")
    assert code_interne == 403, message(
        en=f"GET /interne/compte returns {code_interne}, not 403: "
        f"'expose_interne' in {CONFIG} is probably still true.",
        fr=f"GET /interne/compte retourne {code_interne}, pas 403 : "
        f"'expose_interne' dans {CONFIG} est probablement encore à true.",
    )

    fichier = edge.file(RECETTE)
    assert fichier.exists, message(
        en=f"{RECETTE} does not exist.", fr=f"{RECETTE} n'existe pas."
    )
    try:
        declare = yaml.safe_load(fichier.content_string) or {}
    except yaml.YAMLError as erreur:
        pytest.fail(message(
            en=f"{RECETTE} is not valid YAML: {erreur}",
            fr=f"{RECETTE} n'est pas un YAML valide : {erreur}",
        ))
    for champ in ("dns_ok", "tls_ok", "http_ok", "refus_ok"):
        assert declare.get(champ) is True, message(
            en=f"{RECETTE} must declare '{champ}: true': the matrix really "
            f"passes, your recette must say so honestly.",
            fr=f"{RECETTE} doit déclarer '{champ}: true' : la matrice passe "
            f"réellement, votre recette doit le dire honnêtement.",
        )


def test_restauration_apres_perte(edge, poste, etat) -> None:
    edge_ip = etat["edge_ip"]
    stock_initial = etat["stock_initial"]

    fichier = edge.file(RESTAURER)
    assert fichier.exists, message(
        en=f"{RESTAURER} does not exist: write a restore procedure before "
        f"losing anything, not after.",
        fr=f"{RESTAURER} n'existe pas : écrivez une procédure de restauration "
        f"avant de perdre quoi que ce soit, pas après.",
    )

    # Sauvegarde interne, pour que ce test reste rejouable même si la
    # procédure de l'apprenant échoue en cours de route.
    edge.run("sudo mkdir -p /var/backups/pub-mes-harnais")
    edge.run(f"sudo cp {CONFIG} /var/backups/pub-mes-harnais/route.yaml.bak")
    edge.run(f"sudo cp {STOCK} /var/backups/pub-mes-harnais/stock.json.bak")

    try:
        # Perte contrôlée : la copie active de la configuration et de l'état
        # disparaît, exactement comme l'énoncé la décrit.
        edge.run(f"sudo rm -f {CONFIG} {STOCK}")

        code_perdu, _ = _requete_https(poste, edge_ip, "/catalogue")
        assert code_perdu != 200, message(
            en="The business route still answers 200 after losing the active "
            "configuration and state: the loss was not real.",
            fr="La route métier répond encore 200 après la perte de la "
            "configuration et de l'état actifs : la perte n'était pas réelle.",
        )

        res = edge.run(f"bash {RESTAURER}")
        assert res.rc == 0, message(
            en=f"{RESTAURER} exited with code {res.rc}.\n{res.stdout}\n{res.stderr}",
            fr=f"{RESTAURER} s'est terminé avec le code {res.rc}.\n{res.stdout}\n{res.stderr}",
        )

        code_final = _attendre_code(poste, edge_ip, "/catalogue", 200, 15)
        assert code_final == 200, message(
            en=f"After running {RESTAURER}, /catalogue still does not answer "
            f"200 within 15s (got {code_final}).",
            fr=f"Après avoir exécuté {RESTAURER}, /catalogue ne répond "
            f"toujours pas 200 en 15 s (obtenu {code_final}).",
        )
        _, corps = _requete_https(poste, edge_ip, "/catalogue")
        stock_restaure = (json.loads(corps) if corps else {}).get("stock")
        assert stock_restaure == stock_initial, message(
            en=f"After restoring, /catalogue reports stock={stock_restaure}, "
            f"not the real backed-up value {stock_initial}: this looks like "
            f"a fresh default, not a real restore from backup.",
            fr=f"Après restauration, /catalogue rapporte stock={stock_restaure}, "
            f"pas la vraie valeur sauvegardée {stock_initial} : cela ressemble "
            f"à une valeur par défaut, pas à une vraie restauration depuis la "
            f"sauvegarde.",
        )
    finally:
        edge.run("sudo cp /var/backups/pub-mes-harnais/route.yaml.bak " + CONFIG)
        edge.run("sudo cp /var/backups/pub-mes-harnais/stock.json.bak " + STOCK)
        edge.run(f"sudo rm -f {PURGE}")
        edge.run("sudo systemctl restart pub-mes-router.service")
        _attendre_code(poste, edge_ip, "/catalogue", 200, 15)


def test_rollback_bascule_avec_cache(edge, poste, etat) -> None:
    edge_ip = etat["edge_ip"]

    fichier = edge.file(REVENIR)
    assert fichier.exists, message(
        en=f"{REVENIR} does not exist.", fr=f"{REVENIR} n'existe pas."
    )

    code_nominal, _ = _requete_https(poste, edge_ip, "/catalogue")
    assert code_nominal == 200, message(
        en="The business route does not answer 200 before the injected bad "
        "switch: fix the nominal state first.",
        fr="La route métier ne répond pas 200 avant la bascule injectée : "
        "corrigez d'abord l'état nominal.",
    )

    try:
        edge.run(
            "sudo sed -i 's/^origine_active:.*/origine_active: b/' " + CONFIG
        )
        edge.run(f"sudo rm -f {PURGE}")
        code_casse = _attendre_code(poste, edge_ip, "/catalogue", 500, 30)
        assert code_casse == 500, message(
            en=f"Switching to the invalid candidate origin never produces a "
            f"500 on /catalogue within 30s (got {code_casse}): the cache or "
            f"the router may not read 'origine_active' at all.",
            fr=f"Basculer vers l'origine candidate invalide ne produit jamais "
            f"un 500 sur /catalogue en 30 s (obtenu {code_casse}) : le cache "
            f"ou le routeur ne lit peut-être pas 'origine_active'.",
        )

        debut = time.monotonic()
        res = edge.run(f"bash {REVENIR}")
        assert res.rc == 0, message(
            en=f"{REVENIR} exited with code {res.rc}.\n{res.stdout}\n{res.stderr}",
            fr=f"{REVENIR} s'est terminé avec le code {res.rc}.\n{res.stdout}\n{res.stderr}",
        )
        code_revenu = _attendre_code(poste, edge_ip, "/catalogue", 200, 6)
        duree = time.monotonic() - debut
        assert code_revenu == 200, message(
            en=f"After running {REVENIR}, /catalogue does not answer 200 "
            f"within 6s (got {code_revenu}): the cache ({CONFIG}'s "
            f"'ttl_cache_s') is probably not purged, only route.yaml was "
            f"edited.",
            fr=f"Après avoir exécuté {REVENIR}, /catalogue ne répond pas 200 "
            f"en 6 s (obtenu {code_revenu}) : le cache ('ttl_cache_s' de "
            f"{CONFIG}) n'est probablement pas purgé, seul route.yaml a été "
            f"modifié.",
        )
        assert duree < 6, message(
            en="The rollback only worked by waiting out the cache's TTL, not "
            "by purging it: that is not a documented rollback decision.",
            fr="Le retour en arrière n'a fonctionné qu'en attendant "
            "l'expiration du cache, pas en le purgeant : ce n'est pas une "
            "décision de bascule documentée.",
        )
    finally:
        edge.run(
            "sudo sed -i 's/^origine_active:.*/origine_active: a/' " + CONFIG
        )
        edge.run(f"sudo touch {PURGE}")
        _attendre_code(poste, edge_ip, "/catalogue", 200, 15)


def test_limites_revue_humaine(edge) -> None:
    fichier = edge.file(LIMITES)
    assert fichier.exists, message(
        en=f"{LIMITES} does not exist.", fr=f"{LIMITES} n'existe pas."
    )
    contenu = fichier.content_string.lower()
    requis = {
        "résolveur public": ("résolveur public", "resolveur public", "public resolver"),
        "client externe": ("client externe", "external client"),
        "autorité publique": ("autorité publique", "autorite publique", "ca publique", "public ca"),
        "simulation": ("simulation", "simulé", "simule", "simulated"),
    }
    for titre, variantes in requis.items():
        assert any(v in contenu for v in variantes), message(
            en=f"{LIMITES} never mentions '{titre}' (or an equivalent "
            f"wording): the report must name what a real, Internet-facing "
            f"release would still need to prove.",
            fr=f"{LIMITES} ne mentionne jamais « {titre} » (ni une "
            f"formulation équivalente) : le compte rendu doit nommer ce "
            f"qu'une vraie mise en service exposée sur Internet devrait "
            f"encore prouver.",
        )
    assert len(contenu.strip()) > 80, message(
        en=f"{LIMITES} is too short to be a real review grid.",
        fr=f"{LIMITES} est trop court pour être une vraie grille de revue.",
    )
