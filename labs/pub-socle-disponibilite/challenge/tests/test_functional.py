"""Vérifie, depuis le sondeur fourni (une requête HTTP réelle par point
d'entrée, pas une supposition sur un produit précis), que les deux
backends servent effectivement du trafic en état sain, qu'un backend
malade est retiré de la rotation dans une fenêtre raisonnable, qu'il y
revient une fois rétabli, et que le répartiteur est bien l'unique point
de panne de cette topologie.

Les tests s'enchaînent dans cet ordre et restaurent l'état à chaque
étape (fichier de drapeau retiré, répartiteur redémarré), pour que la
suite reste rejouable telle quelle par le validateur, dans les deux sens
(avant et après la solution).
"""

from __future__ import annotations

import json
import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
ETAT = "/var/lib/pub-disp/etat.json"
SCRIPT = "/opt/pub-disp/sonder.py"
MALSAIN_A = "/var/lib/pub-disp/malsain-a"
MALSAIN_B = "/var/lib/pub-disp/malsain-b"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


def _sonder(edge, *args: str) -> dict:
    cmd = "sudo -u student python3 " + SCRIPT + " " + " ".join(str(a) for a in args)
    res = edge.run(cmd)
    assert res.rc == 0, message(
        en=f"The provided probe failed (rc={res.rc}): {res.stderr}",
        fr=f"Le sondeur fourni a échoué (rc={res.rc}) : {res.stderr}",
    )
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        pytest.fail(
            message(
                en=f"The probe did not print valid JSON: {res.stdout!r}",
                fr=f"Le sondeur n'a pas imprimé de JSON valide : {res.stdout!r}",
            )
        )


def test_repartition_deux_instances_saines(edge, etat):
    """Un échantillon de trafic via le répartiteur montre bien les deux
    identités de backend, sans alternance exacte imposée."""
    sortie = _sonder(edge, "echantillon", etat["repartiteur_port"], "8")
    identites = set(sortie["identites"])
    assert identites == {"a", "b"}, message(
        en=f"Only these backend identities were seen through the balancer "
        f"in 8 requests, with both backends healthy: {identites}. The "
        f"balancer is probably still stuck on a single instance.",
        fr=f"Seules ces identités de backend ont été vues via le "
        f"répartiteur en 8 requêtes, les deux backends étant sains : "
        f"{identites}. Le répartiteur est probablement encore collé à "
        f"une seule instance.",
    )


def test_retrait_backend_malade(edge, etat):
    """Un backend rendu malade est retiré de la rotation dans une fenêtre
    raisonnable : le trafic ne lui est plus jamais envoyé une fois cette
    fenêtre passée."""
    try:
        edge.run(f"sudo touch {MALSAIN_A}")
        limite = time.monotonic() + 12
        identites: set[str] = set()
        while time.monotonic() < limite:
            sortie = _sonder(edge, "echantillon", etat["repartiteur_port"], "4")
            identites = set(sortie["identites"])
            if "a" not in identites:
                break
            time.sleep(1)
        assert "a" not in identites, message(
            en="Backend a kept receiving traffic through the balancer "
            "12s after being marked sick: the removal probe is probably "
            "still too slow or too tolerant.",
            fr="Le backend a a continué à recevoir du trafic via le "
            "répartiteur 12 s après avoir été marqué malade : la sonde "
            "de retrait est probablement encore trop lente ou trop "
            "tolérante.",
        )
        assert "b" in identites, message(
            en="No traffic reached the remaining healthy backend b once a "
            "was removed.",
            fr="Aucun trafic n'a atteint le backend b, resté sain, une "
            "fois a retiré.",
        )
    finally:
        edge.run(f"sudo rm -f {MALSAIN_A}")


def test_retour_backend_retabli(edge, etat):
    """Une fois retiré pour cause de panne puis rétabli, le backend
    revient réellement dans la rotation dans une fenêtre raisonnable."""
    try:
        edge.run(f"sudo touch {MALSAIN_A}")
        limite_retrait = time.monotonic() + 12
        identites: set[str] = set()
        while time.monotonic() < limite_retrait:
            sortie = _sonder(edge, "echantillon", etat["repartiteur_port"], "4")
            identites = set(sortie["identites"])
            if "a" not in identites:
                break
            time.sleep(1)
        assert "a" not in identites, message(
            en="Backend a was never actually removed from rotation, so "
            "its return cannot be meaningfully observed.",
            fr="Le backend a n'a jamais été réellement retiré de la "
            "rotation : son retour ne peut pas être observé de façon "
            "significative.",
        )

        edge.run(f"sudo rm -f {MALSAIN_A}")
        limite_retour = time.monotonic() + 12
        while time.monotonic() < limite_retour:
            sortie = _sonder(edge, "echantillon", etat["repartiteur_port"], "4")
            identites = set(sortie["identites"])
            if "a" in identites:
                break
            time.sleep(1)
        assert "a" in identites, message(
            en="Backend a never came back into rotation within 12s after "
            "recovering: the return threshold is probably still far too "
            "high.",
            fr="Le backend a n'est jamais revenu dans la rotation en "
            "12 s après son rétablissement : le seuil de retour est "
            "probablement encore beaucoup trop haut.",
        )
    finally:
        edge.run(f"sudo rm -f {MALSAIN_A}")


def test_point_unique_de_panne(edge, etat):
    """Le répartiteur est le seul point d'entrée : l'arrêter rend les
    deux backends injoignables par ce chemin, alors qu'ils répondent
    toujours directement. Le répartiteur est redémarré dans tous les
    cas après ce test."""
    avant = _sonder(edge, "echantillon", etat["repartiteur_port"], "4")
    assert set(avant["identites"]) == {"a", "b"}, message(
        en="Both backends were not reachable through the balancer before "
        "stopping it: the demonstration would not prove anything.",
        fr="Les deux backends n'étaient pas joignables via le "
        "répartiteur avant de l'arrêter : la démonstration ne "
        "prouverait rien.",
    )
    try:
        edge.run("sudo systemctl stop pub-disp-repartiteur.service")
        joignable = _sonder(edge, "indisponible", etat["repartiteur_port"])
        assert not joignable["joignable"], message(
            en="The balancer port is still reachable after stopping the "
            "service.",
            fr="Le port du répartiteur reste joignable après l'arrêt du "
            "service.",
        )
        direct_a = _sonder(edge, "direct", etat["port_a"])
        direct_b = _sonder(edge, "direct", etat["port_b"])
        assert direct_a.get("corps") == {"backend": "a"}, message(
            en=f"Backend a is not reachable directly while the balancer "
            f"is down: {direct_a}",
            fr=f"Le backend a n'est pas joignable directement alors que "
            f"le répartiteur est arrêté : {direct_a}",
        )
        assert direct_b.get("corps") == {"backend": "b"}, message(
            en=f"Backend b is not reachable directly while the balancer "
            f"is down: {direct_b}",
            fr=f"Le backend b n'est pas joignable directement alors que "
            f"le répartiteur est arrêté : {direct_b}",
        )
    finally:
        edge.run("sudo systemctl start pub-disp-repartiteur.service")
