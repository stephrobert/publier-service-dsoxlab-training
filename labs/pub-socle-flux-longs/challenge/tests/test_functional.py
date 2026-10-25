"""Vérifie, depuis le client de mesure fourni (chronométrage réel, pas
lecture d'un corps final), que l'aller-retour WebSocket répond vite, que
les événements SSE arrivent au fil de l'eau et pas seulement à la
fermeture du flux, que le heartbeat respecte l'intervalle attendu, et
qu'une panne du producteur est signalée clairement au flux SSE plutôt que
de le laisser pendre indéfiniment.

Chaque vérification lance `mesure_flux.py` (asyncio + websockets, déjà
installé sur edge.lab par `prepare.sh`) depuis edge.lab lui-même, puisque
tout tourne en boucle locale (127.0.0.1). Le test de panne arrête le
service `pub-flux-producteur` : il tourne en dernier et le redémarre dans
tous les cas, pour ne pas affecter les tests suivants ni une relecture
ultérieure de cette suite.
"""

from __future__ import annotations

import json

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
ETAT = "/var/lib/pub-flux/etat.json"
SCRIPT = "/opt/pub-flux/mesure_flux.py"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


def _mesurer(edge, *args: str) -> dict:
    cmd = "sudo -u student python3 " + SCRIPT + " " + " ".join(str(a) for a in args)
    res = edge.run(cmd)
    assert res.rc == 0, message(
        en=f"The provided measuring client failed (rc={res.rc}): {res.stderr}",
        fr=f"Le client de mesure fourni a échoué (rc={res.rc}) : {res.stderr}",
    )
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        pytest.fail(
            message(
                en=f"The measuring client did not print valid JSON: {res.stdout!r}",
                fr=f"Le client de mesure n'a pas imprimé de JSON valide : {res.stdout!r}",
            )
        )


def test_websocket_aller_retour(edge, etat):
    """Un message envoyé sur le WebSocket revient en écho en moins d'une
    seconde : l'échange est réellement bidirectionnel après la poignée de
    main, pas différé par un délai artificiel."""
    sortie = _mesurer(edge, "websocket", etat["ws_port"])
    assert sortie["reponse"] == "echo:ping", message(
        en=f"The WebSocket did not echo the sent message: {sortie}",
        fr=f"Le WebSocket n'a pas renvoyé le message envoyé en écho : {sortie}",
    )
    assert sortie["aller_retour_ms"] < 1000, message(
        en=f"The WebSocket round trip took {sortie['aller_retour_ms']} ms: "
        f"an echo delay is probably still injected.",
        fr=f"L'aller-retour WebSocket a pris {sortie['aller_retour_ms']} ms : "
        f"un délai d'écho est probablement encore injecté.",
    )


def test_sse_evenements_progressifs(edge, etat):
    """Les notifications arrivent sur le flux SSE au fil de l'eau, une par
    seconde, et pas seulement groupées à la fin de la fenêtre
    d'observation : le tampon ne doit pas retenir les événements."""
    sortie = _mesurer(edge, "sse", etat["sse_port"], "4")
    donnees = [e for e in sortie["evenements"] if e["type"] == "donnee"]
    assert len(donnees) >= 2, message(
        en=f"Fewer than 2 data events arrived within 4s: {sortie['evenements']}",
        fr=f"Moins de 2 événements de données sont arrivés en 4 s : "
        f"{sortie['evenements']}",
    )
    ecarts = [b["t"] - a["t"] for a, b in zip(donnees, donnees[1:])]
    assert all(ecart < 2.5 for ecart in ecarts), message(
        en=f"Data events arrived bunched together instead of progressively: "
        f"gaps {ecarts}s between consecutive events.",
        fr=f"Les événements de données sont arrivés groupés au lieu de "
        f"progressivement : écarts de {ecarts} s entre événements "
        f"consécutifs.",
    )


def test_inactivite_heartbeat(edge, etat):
    """En l'absence de nouvelle notification, le flux SSE émet un
    heartbeat dans un délai raisonnable : un intervalle trop long ou
    jamais déclenché laisse le client incapable de distinguer un flux
    silencieux d'un flux mort."""
    sortie = _mesurer(edge, "sse", etat["sse_port"], "5")
    heartbeats = [e for e in sortie["evenements"] if e["type"] == "heartbeat"]
    assert heartbeats, message(
        en=f"No heartbeat arrived within 5s: {sortie['evenements']}",
        fr=f"Aucun heartbeat n'est arrivé en 5 s : {sortie['evenements']}",
    )
    assert heartbeats[0]["t"] < 4, message(
        en=f"The first heartbeat took {heartbeats[0]['t']}s: the interval "
        f"is probably still far too long.",
        fr=f"Le premier heartbeat a pris {heartbeats[0]['t']} s : "
        f"l'intervalle est probablement encore beaucoup trop long.",
    )


def test_panne_signalee(edge, etat):
    """Quand le producteur tombe, le flux SSE le signale explicitement
    (un événement dédié) puis se ferme, plutôt que de laisser le client
    attendre indéfiniment sans explication. Le producteur est redémarré
    dans tous les cas après ce test."""
    try:
        sortie = _mesurer(edge, "panne", etat["sse_port"], "1", "6")
    finally:
        edge.run("sudo systemctl start pub-flux-producteur.service")

    types = [e["type"] for e in sortie["evenements"]]
    assert "panne" in types, message(
        en=f"No dedicated failure event was sent when the backend stopped: "
        f"{sortie['evenements']}",
        fr=f"Aucun événement de panne dédié n'a été envoyé à l'arrêt du "
        f"backend : {sortie['evenements']}",
    )
    assert "fermeture" in types, message(
        en=f"The SSE stream was not closed after signaling the failure: "
        f"{sortie['evenements']}",
        fr=f"Le flux SSE ne s'est pas fermé après avoir signalé la panne : "
        f"{sortie['evenements']}",
    )
