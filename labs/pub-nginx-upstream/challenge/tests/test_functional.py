"""Verify load sharing, passive detection, return to service, and that the
retry policy never duplicates a non-idempotent action.

CE QUE LE BUILD OPEN SOURCE PERMET, ET CE QU'IL NE PERMET PAS

Nginx open source n'a AUCUNE sonde active : il ne va pas interroger un
backend pour savoir s'il va bien. La seule detection disponible est passive,
`max_fails` et `fail_timeout`, et elle se declenche sur de vraies requetes
de clients. Autrement dit, les premieres requetes partent SUR le backend
fautif avant qu'il ne soit retire. Le deuxieme test mesure donc qu'il CESSE
d'en recevoir, et non qu'il n'en a jamais recu : exiger zero requete fautive
serait exiger du build open source ce qu'il ne sait pas faire.

OU LA DETECTION SE MESURE, ET POURQUOI PAS CHEZ LE CLIENT

`proxy_next_upstream error timeout http_502` rattrape le 502 du backend
fautif sur l'autre backend : le client recoit un 200 qu'il y ait eu retrait
ou non. Compter ses erreurs mesure donc le rattrapage, pas la detection, et
c'est ce qui faisait passer ce test sur l'etat de depart avant le
2026-10-26. La mesure est prise la ou la difference existe, sur le backend,
par les compteurs `vus-a.txt` et `vus-b.txt` du banc.
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


def _vus(edge, backend: str) -> int:
    """Le nombre de requetes RECUES par un backend, lu sur le banc.

    C'est la seule mesure qui dise si un backend est encore SOLLICITE. Vu
    du client, un backend retire et un backend fautif dont les 502 sont
    rattrapes par `proxy_next_upstream` sont indiscernables : dans les deux
    cas, c'est l'autre backend qui rend le 200.
    """
    brut = edge.run(f"sudo cat {WORK}/vus-{backend}.txt").stdout.strip()
    try:
        return int(brut)
    except ValueError:
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


def test_le_backend_fautif_cesse_d_etre_sollicite(edge, poste, ip_edge) -> None:
    """La detection se mesure SUR LE BACKEND, pas chez le client.

    Mesure du 2026-10-26 : la version precedente de ce test comptait les
    erreurs vues par le client sur la seconde moitie d'une rafale, et elle
    passait sur l'etat de depart, ou rien n'est jamais retire. La cause
    n'etait pas le test : `proxy_next_upstream error timeout http_502`
    rattrape le 502 du backend fautif sur l'autre backend, si bien que le
    client recoit un 200 dans les deux cas. Compter les erreurs du client
    ne mesurait donc pas la detection, mais le rattrapage.

    Ce qui distingue reellement les deux etats, c'est que le backend retire
    ne RECOIT plus rien. La detection passive apprend des requetes des
    clients, donc les premieres erreurs sont bien servies : la premiere
    rafale sert a apprendre, la seconde a mesurer.
    """
    _mode(edge, "a", "erreur")
    time.sleep(1)

    apprentissage = _rafale(poste, ip_edge, 20)
    assert len(apprentissage) >= 10, message(
        en="The burst produced too few answers for the measurement to mean anything.",
        fr="La rafale a produit trop peu de réponses pour que la mesure signifie "
        "quelque chose.",
    )
    pivot = _vus(edge, "a")
    assert pivot >= 0, message(
        en=f"The per-backend counter {WORK}/vus-a.txt could not be read.",
        fr=f"Le compteur du banc {WORK}/vus-a.txt n'a pas pu être lu.",
    )

    reponses = _rafale(poste, ip_edge, 20)
    recues = _vus(edge, "a") - pivot

    # Une retentative par fenetre de `fail_timeout` est NORMALE, et c'est
    # meme ainsi que le backend revient : on tolere donc quelques requetes,
    # pas un flux continu.
    #
    # Le seuil est mesure, pas devine. Banc local du 2026-10-26, meme nginx
    # 1.31.8, meme backends : avec `max_fails=2 fail_timeout=10s`, le
    # backend retire recoit 2 requetes sur 20 (les retentatives de fin de
    # fenetre) ; sur l'etat de depart il en recoit 20 sur 20, et 10 sur 20
    # si l'on retire `backup` sans donner de valeur a `max_fails`. Cinq
    # separe les trois cas en gardant de la marge des deux cotes.
    assert recues <= 5, message(
        en=(
            f"The faulty backend still received {recues} of the last "
            f"{len(reponses)} requests. Passive detection is disabled: "
            "`max_fails=0` means never remove. Give `max_fails` and "
            "`fail_timeout` values you can justify. Note that the client sees "
            "no error either way, because the retry hides it on the other "
            "backend: what is measured here is what the backend receives."
        ),
        fr=(
            f"Le backend fautif a encore reçu {recues} des {len(reponses)} "
            "dernières requêtes. La détection passive est désactivée : "
            "`max_fails=0` veut dire « ne jamais retirer ». Donnez à "
            "`max_fails` et `fail_timeout` des valeurs que vous savez "
            "justifier. Notez que le client ne voit d'erreur ni dans un cas ni "
            "dans l'autre, le rejeu la masquant sur l'autre backend : ce qui "
            "est mesuré ici, c'est ce que le backend reçoit."
        ),
    )

    # Et le service reste debout : un retrait qui coupe le service n'est pas
    # une detection reussie.
    servies = [r for r in reponses if r.startswith("backend=") and "erreur" not in r]
    assert len(servies) >= len(reponses) - 1, message(
        en=(
            f"Only {len(servies)} of {len(reponses)} requests were served while "
            "one backend was faulty. Removing a backend must not take the "
            "service with it: the other one is there for that."
        ),
        fr=(
            f"Seules {len(servies)} requêtes sur {len(reponses)} ont été "
            "servies alors qu'un seul backend était fautif. Retirer un backend "
            "ne doit pas emporter le service : l'autre est là pour ça."
        ),
    )


def test_le_backend_revient_au_trafic_apres_fail_timeout(
    edge, poste, ip_edge
) -> None:
    """Un retrait definitif n'est pas une detection, c'est une suppression.

    Apres `fail_timeout`, Nginx retente le backend retire. S'il repond, il
    reprend sa part. Le test attend donc le delai declare, puis exige de
    revoir le backend.

    IL EXIGE D'ABORD LE RETRAIT, et c'est la correction du 2026-10-26 :
    sans elle, ce test passait sur l'etat de depart. La raison est logique
    plutot que technique : la ou rien n'est jamais retire, le backend est
    toujours la, donc « il est revenu » est vrai sans que rien n'ait eu
    lieu. Un retour ne se mesure qu'apres un depart.
    """
    _mode(edge, "a", "erreur")
    time.sleep(1)
    _rafale(poste, ip_edge, 20)
    pivot = _vus(edge, "a")
    _rafale(poste, ip_edge, 20)
    recues = _vus(edge, "a") - pivot
    assert recues <= 5, message(
        en=(
            f"The faulty backend was never removed: it still received {recues} "
            "of the last 20 requests. There is nothing to come back from until "
            "`max_fails` removes it, so give it a value first."
        ),
        fr=(
            f"Le backend fautif n'a jamais été retiré : il a encore reçu "
            f"{recues} des 20 dernières requêtes. Il n'y a rien à faire "
            "revenir tant que `max_fails` ne le retire pas : donnez-lui "
            "d'abord une valeur."
        ),
    )

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
