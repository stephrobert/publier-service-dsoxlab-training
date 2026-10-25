"""Vérifie le diagnostic, la réparation et la sécurité du lab
pub-socle-depannage.

Un seul fait secret commande ce lab : la couche réellement cassée, tirée au
sort par `fixtures/prepare.sh` et conservée hors de portée de l'apprenant
dans `/root/.pub-dep-secret.yaml`. Les tests comparent le diagnostic écrit à
ce secret, jamais à un texte libre jugé au jugé.

Chaque test qui dépend d'un état durable le lit depuis `edge.lab` (où tourne
le banc) et observe depuis `poste.lab` (le client indépendant) quand le
point de vue du client est ce qui compte réellement.
"""

from __future__ import annotations

import re

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
NOM = "depan.test"
JOURNAL = "/home/student/journal.md"
DIAGNOSTIC = "/home/student/diagnostic.yaml"
COUCHES = {"dns", "transport", "tls", "route", "backend"}


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def etat(edge):
    return yaml.safe_load(edge.run("sudo cat /var/lib/pub-dep/etat.json").stdout)


@pytest.fixture(scope="module")
def secret(edge):
    return yaml.safe_load(edge.run("sudo cat /root/.pub-dep-secret.yaml").stdout)


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


def test_hypothese_formulee_et_testee(edge) -> None:
    """Revue humaine assistée : le journal porte des observations
    horodatées, une hypothèse énoncée, et son issue (confirmée ou
    réfutée) par un test ciblé. Le contenu réel du raisonnement reste
    affaire de relecture humaine ; ce contrôle vérifie seulement que la
    méthode a laissé une trace, pas qu'elle est la bonne.
    """
    res = edge.run(f"cat {JOURNAL}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{JOURNAL} does not exist or is empty: the investigation must leave "
        f"a written trail.",
        fr=f"{JOURNAL} n'existe pas ou est vide : l'enquête doit laisser une "
        f"trace écrite.",
    )
    contenu = res.stdout
    horodatages = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", contenu)
    assert len(horodatages) >= 2, message(
        en=f"{JOURNAL} must carry at least two timestamped observations "
        f"(HH:MM), not an undated narrative.",
        fr=f"{JOURNAL} doit porter au moins deux observations horodatées "
        f"(HH:MM), pas un récit sans dates.",
    )
    bas = contenu.lower()
    a_hypothese = any(mot in bas for mot in ("hypothese", "hypothèse"))
    a_test = "test" in bas
    a_issue = any(
        mot in bas
        for mot in (
            "confirmee", "confirmée", "confirme",
            "refutee", "réfutée", "infirmee", "infirmée", "invalidee", "invalidée",
        )
    )
    assert a_hypothese and a_test and a_issue, message(
        en=f"{JOURNAL} must state a hypothesis, the targeted test that was run, "
        f"and whether it was confirmed or refuted.",
        fr=f"{JOURNAL} doit énoncer une hypothèse, le test ciblé mené, et si "
        f"elle a été confirmée ou réfutée.",
    )


def test_cause_couche_et_composant_identifies(edge, secret) -> None:
    """La couche doit correspondre exactement à la variante secrète (un
    champ structuré, pas une recherche de mots dans un texte libre), et le
    composant doit nommer le mot-clé propre à cette couche, sans
    reprendre aussi ceux des quatre autres : une réponse qui couvre toutes
    les couches à la fois ne prouve aucun diagnostic.
    """
    res = edge.run(f"cat {DIAGNOSTIC}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{DIAGNOSTIC} does not exist or is empty.",
        fr=f"{DIAGNOSTIC} n'existe pas ou est vide.",
    )
    diagnostic = yaml.safe_load(res.stdout) or {}
    couche = str(diagnostic.get("couche", "")).strip().lower()
    composant = str(diagnostic.get("composant", "")).strip().lower()

    assert couche in COUCHES, message(
        en=f"{DIAGNOSTIC}'s 'couche' field must be one of {sorted(COUCHES)}, got "
        f"{couche!r}.",
        fr=f"Le champ 'couche' de {DIAGNOSTIC} doit valoir l'une de "
        f"{sorted(COUCHES)}, pas {couche!r}.",
    )
    assert couche == secret["fault"], message(
        en=f"{DIAGNOSTIC} names layer {couche!r}, but the actual fault is on a "
        f"different layer.",
        fr=f"{DIAGNOSTIC} nomme la couche {couche!r}, mais la panne réelle est "
        f"sur une autre couche.",
    )
    assert secret["mot_cle"] in composant, message(
        en=f"{DIAGNOSTIC}'s 'composant' field never names the actual faulty "
        f"component on edge.lab.",
        fr=f"Le champ 'composant' de {DIAGNOSTIC} ne nomme jamais le composant "
        f"réellement fautif sur edge.lab.",
    )
    for autre in secret["mots_cle_autres"]:
        assert autre not in composant, message(
            en=f"{DIAGNOSTIC}'s 'composant' field also names an unrelated layer "
            f"({autre!r}): naming every layer at once is not a diagnosis.",
            fr=f"Le champ 'composant' de {DIAGNOSTIC} nomme aussi une couche "
            f"sans rapport ({autre!r}) : tout citer à la fois n'est pas un "
            f"diagnostic.",
        )


def test_reparation_et_non_regression(edge, poste, etat) -> None:
    """Après correction, le service répond, et répond encore face à une
    nouvelle salve de contrôles : une seule requête qui passe par chance
    ne prouve rien.
    """
    edge_ip = etat["edge_ip"]

    dig = poste.run(f"dig +short {NOM} A").stdout.strip().splitlines()
    assert edge_ip in dig, message(
        en=f"'dig {NOM} A' from poste.lab does not return {edge_ip}: got {dig}.",
        fr=f"'dig {NOM} A' depuis poste.lab ne retourne pas {edge_ip} : obtenu "
        f"{dig}.",
    )

    for essai in range(3):
        code, _ = _requete_https(poste, edge_ip, "/")
        assert code == 200, message(
            en=f"Attempt {essai + 1}/3: https://{NOM}/ returns {code}, not 200.",
            fr=f"Essai {essai + 1}/3 : https://{NOM}/ répond {code}, pas 200.",
        )


def test_securite_aucune_protection_retiree(edge, poste, etat) -> None:
    """Propriété critique : réparer la panne tirée au sort n'a dégradé ni
    la route interdite, ni l'isolement du backend, ni l'obligation TLS.
    """
    edge_ip = etat["edge_ip"]
    backend_port = etat["backend_port"]

    code, _ = _requete_https(poste, edge_ip, "/admin")
    assert code == 403, message(
        en=f"https://{NOM}/admin must still be refused (403) after the repair, "
        f"got {code}.",
        fr=f"https://{NOM}/admin doit encore être refusée (403) après la "
        f"correction, obtenu {code}.",
    )

    direct = poste.run(
        f"curl -s --max-time 3 http://{edge_ip}:{backend_port}/"
    )
    assert not direct.stdout.strip(), message(
        en=f"The backend on port {backend_port} is now directly reachable from "
        f"poste.lab: the repair must not expose it.",
        fr=f"Le backend sur le port {backend_port} est maintenant joignable "
        f"directement depuis poste.lab : la correction ne doit pas l'exposer.",
    )

    brut = poste.run(
        f"timeout 3 bash -c 'exec 3<>/dev/tcp/{edge_ip}/443; "
        f"printf \"GET / HTTP/1.0\\r\\n\\r\\n\" >&3; cat <&3' 2>/dev/null || true"
    )
    assert "HTTP/1." not in brut.stdout, message(
        en="Port 443 answers plain HTTP without TLS: the repair must not "
        "downgrade the entry point to drop TLS.",
        fr="Le port 443 répond en HTTP en clair, sans TLS : la correction ne "
        "doit pas faire perdre TLS au point d'entrée.",
    )
