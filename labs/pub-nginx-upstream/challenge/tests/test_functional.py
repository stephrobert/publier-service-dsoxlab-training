"""Verify load sharing, passive detection, return to service, and that the
retry policy never duplicates a non-idempotent action.

CE QUE LE BUILD OPEN SOURCE PERMET, ET CE QU'IL NE PERMET PAS

Nginx open source n'a AUCUNE sonde active : il ne va pas interroger un
backend pour savoir s'il va bien. La seule detection disponible est passive,
`max_fails` et `fail_timeout`, et elle se declenche sur de vraies requetes
de clients. Autrement dit, les premieres erreurs sont SERVIES avant que le
backend ne soit retire. Le deuxieme test mesure donc que les erreurs
CESSENT, et non qu'il n'y en a jamais eu : exiger zero erreur serait exiger
du build open source ce qu'il ne sait pas faire.
"""

from __future__ import annotations

import json
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
WORK = "/opt/pub-nginx-upstream"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _mode(edge, backend: str, valeur: str) -> None:
    edge.run(f"echo {valeur} | sudo tee {WORK}/mode-{backend}.txt >/dev/null")


def _rafale(poste, ip: str, nombre: int = 20) -> list[str]:
    """Le corps de chaque reponse, pour savoir QUI a repondu."""
    sortie = poste.run(
        f"for i in $(seq 1 {nombre}); do "
        f"curl -s --max-time 12 http://{ip}/ || echo 'echec'; done"
    ).stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def _commandes(edge) -> int:
    brut = edge.run(f"sudo cat {WORK}/commandes.json").stdout.strip()
    try:
        return int(json.loads(brut).get("commandes", -1))
    except (json.JSONDecodeError, AttributeError, ValueError):
        return -1


@pytest.fixture(autouse=True)
def _remettre_les_modes(edge):
    """Chaque test part de deux backends sains, et les rend sains en partant.

    Sans cela, un test qui echoue laisse un backend en erreur et fait
    echouer le suivant pour une raison qui n'est pas la sienne.
    """
    _mode(edge, "a", "ok")
    _mode(edge, "b", "ok")
    time.sleep(1)
    yield
    _mode(edge, "a", "ok")
    _mode(edge, "b", "ok")


def test_les_deux_backends_recoivent_du_trafic_en_etat_sain(poste, ip_edge) -> None:
    """La repartition existe : les deux noms apparaissent."""
    reponses = _rafale(poste, ip_edge, 20)
    vus = {r.split("=", 1)[1].split()[0] for r in reponses if r.startswith("backend=")}
    assert vus == {"a", "b"}, message(
        en=(
            f"Over 20 requests, only {sorted(vus) or 'nothing'} answered. Both "
            "backends must receive traffic while healthy, otherwise there is "
            "no sharing to speak of."
        ),
        fr=(
            f"Sur 20 requêtes, seul {sorted(vus) or 'rien'} a répondu. Les deux "
            "backends doivent recevoir du trafic en état sain, sans quoi il n'y "
            "a pas de répartition."
        ),
    )


def test_les_erreurs_cessent_apres_detection_du_backend_fautif(
    edge, poste, ip_edge
) -> None:
    """Les erreurs CESSENT : on ne demande pas qu'il n'y en ait jamais eu.

    La detection passive apprend des requetes des clients. Les premieres
    erreurs sont donc servies, et c'est une propriete du build open source,
    pas un defaut de la configuration. On mesure le retrait sur la SECONDE
    moitie de la rafale.
    """
    _mode(edge, "a", "erreur")
    time.sleep(1)

    reponses = _rafale(poste, ip_edge, 30)
    seconde_moitie = reponses[15:]
    restantes = [r for r in seconde_moitie if "erreur" in r or "echec" in r]

    assert len(seconde_moitie) >= 10, message(
        en="The burst produced too few answers for the measurement to mean anything.",
        fr="La rafale a produit trop peu de réponses pour que la mesure signifie "
        "quelque chose.",
    )
    assert not restantes, message(
        en=(
            f"{len(restantes)} of the last {len(seconde_moitie)} requests still "
            "hit the faulty backend. Passive detection is disabled: "
            "`max_fails=0` means never remove. Give `max_fails` and "
            "`fail_timeout` values you can justify."
        ),
        fr=(
            f"{len(restantes)} des {len(seconde_moitie)} dernières requêtes "
            "touchent encore le backend fautif. La détection passive est "
            "désactivée : `max_fails=0` veut dire « ne jamais retirer ». Donnez "
            "à `max_fails` et `fail_timeout` des valeurs que vous savez "
            "justifier."
        ),
    )


def test_le_backend_revient_au_trafic_apres_fail_timeout(
    edge, poste, ip_edge
) -> None:
    """Un retrait definitif n'est pas une detection, c'est une suppression.

    Apres `fail_timeout`, Nginx retente le backend retire. S'il repond, il
    reprend sa part. Le test attend donc le delai declare, puis exige de
    revoir le backend.
    """
    _mode(edge, "a", "erreur")
    _rafale(poste, ip_edge, 20)
    _mode(edge, "a", "ok")

    # On laisse passer la fenetre la plus longue qu'une reponse raisonnable
    # puisse declarer, puis on cherche le retour.
    revenu = False
    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        reponses = _rafale(poste, ip_edge, 10)
        if any("backend=a" in r for r in reponses):
            revenu = True
            break
        time.sleep(5)

    assert revenu, message(
        en=(
            "The backend never came back into rotation after it became healthy "
            "again. A permanent removal is not detection, it is deletion: "
            "`fail_timeout` is also the delay after which Nginx tries again."
        ),
        fr=(
            "Le backend n'est jamais revenu dans la rotation après être "
            "redevenu sain. Un retrait définitif n'est pas une détection mais "
            "une suppression : `fail_timeout` est aussi le délai au bout duquel "
            "Nginx retente."
        ),
    )


def test_la_politique_de_rejeu_ne_double_pas_une_action(
    edge, poste, ip_edge
) -> None:
    """CRITIQUE. Le backend ecrit PUIS echoue : rejouer compte deux fois.

    Le compteur metier est le seul temoin : le client recoit une erreur dans
    les deux cas, qu'une commande ait ete enregistree une fois ou deux.
    """
    _mode(edge, "a", "erreur")
    time.sleep(1)
    avant = _commandes(edge)
    assert avant >= 0, message(
        en="The business counter could not be read.",
        fr="Le compteur métier n'a pas pu être lu.",
    )

    # On vise le backend fautif en insistant : la repartition etant alternee,
    # quelques POST suffisent pour qu'au moins un parte sur `a`.
    poste.run(
        f"for i in 1 2 3 4; do "
        f"curl -s -o /dev/null --max-time 12 -X POST http://{ip_edge}/; done"
    )
    time.sleep(2)
    apres = _commandes(edge)
    envoyees = 4

    assert apres - avant <= envoyees, message(
        en=(
            f"{envoyees} orders were sent and the counter moved by "
            f"{apres - avant}. At least one was replayed on the other backend "
            "after the first had already written it. Remove `non_idempotent` "
            "from `proxy_next_upstream`: the caller cannot tell a lost answer "
            "from an action that never happened, so a POST is not retried."
        ),
        fr=(
            f"{envoyees} commandes ont été envoyées et le compteur a bougé de "
            f"{apres - avant}. Au moins une a été rejouée sur l'autre backend "
            "après que le premier l'eut déjà écrite. Retirez `non_idempotent` "
            "de `proxy_next_upstream` : l'appelant ne distingue pas une réponse "
            "perdue d'une action qui n'a pas eu lieu, donc un POST ne se rejoue "
            "pas."
        ),
    )
