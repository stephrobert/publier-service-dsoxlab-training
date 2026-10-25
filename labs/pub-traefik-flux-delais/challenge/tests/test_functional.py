"""Vérifie les délais, le flux et la politique de retry que Traefik
applique devant les backends du lab :

- une attente légitime et bornée réussit, une panne persistante échoue
  dans un délai borné plutôt que de faire attendre indéfiniment ;
- un flux SSE et un WebSocket échangent réellement des données avant
  qu'un délai de réponse trop court ne les coupe ;
- un backend devenu malsain est retiré de la rotation sans pénaliser
  les requêtes envoyées aux backends sains ;
- une action métier non idempotente (POST) n'est jamais rejouée par une
  politique de retry, même quand sa réponse est perdue après une
  écriture déjà réussie côté serveur (point critique).

Le test de retrait bascule l'état de santé du backend b : il restaure
systématiquement ce fichier dans un `finally`, pour ne pas laisser un
backend injoignable corrompre une exécution suivante de cette suite,
sur la même VM.
"""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
MESURE = "/opt/pub-flux/app/mesure_ws.py"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _curl(edge, host: str, chemin: str, methode: str = "GET", max_time: int = 10) -> object:
    return edge.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' -X {methode} "
        f"--max-time {max_time} -H 'Host: {host}' http://127.0.0.1{chemin}"
    )


def test_delais_bornes_sans_casser_le_legitime(edge) -> None:
    legitime = _curl(edge, "api.flux.lab.test", "/lent?ms=1500", max_time=4)
    assert legitime.stdout == "200", message(
        en=f"A legitimate 1.5s delay must succeed: got {legitime.stdout!r}. "
        "Transport timeouts that are too strict would break normal use.",
        fr=f"Une attente légitime de 1,5 s doit réussir : reçu "
        f"{legitime.stdout!r}. Des délais de transport trop stricts "
        "casseraient l'usage normal.",
    )

    panne = _curl(edge, "api.flux.lab.test", "/bloque", max_time=10)
    assert panne.stdout in {"502", "504"}, message(
        en=f"A backend that never answers must fail with a bounded gateway "
        f"error within 10s, not hang: got {panne.stdout!r} (likely a client "
        "abort, meaning Traefik itself never gave up). Bound "
        "serversTransports.lent.forwardingTimeouts.",
        fr=f"Un backend qui ne répond jamais doit échouer par une erreur de "
        f"passerelle bornée en 10 s, pas pendre : reçu {panne.stdout!r} "
        "(probablement un abandon côté client, signe que Traefik lui-même "
        "n'a jamais renoncé). Bornez "
        "serversTransports.lent.forwardingTimeouts.",
    )


def test_flux_echange_reellement_des_donnees(edge) -> None:
    sse = edge.run(
        "timeout 7 curl -s --max-time 5 -H 'Host: flux.lab.test' "
        "http://127.0.0.1/events"
    )
    lignes = [l for l in sse.stdout.splitlines() if l.startswith("data:")]
    assert len(lignes) >= 4, message(
        en=f"Only {len(lignes)} SSE event(s) arrived in a 5s window: the "
        "entry point's writeTimeout is probably still cutting the stream "
        "too early. Raise entryPoints.web.transport.respondingTimeouts."
        "writeTimeout.",
        fr=f"Seulement {len(lignes)} événement(s) SSE sont arrivés en 5 s : "
        "le writeTimeout du point d'entrée coupe probablement encore le "
        "flux trop tôt. Augmentez entryPoints.web.transport."
        "respondingTimeouts.writeTimeout.",
    )

    ws = edge.run(f"python3 {MESURE} flux.lab.test 80 /ws 0")
    import json

    sortie = json.loads(ws.stdout.strip().splitlines()[-1])
    assert sortie["erreur"] is None and sortie["echo"] == "echo:ping", message(
        en=f"The WebSocket did not echo the sent message: {sortie}",
        fr=f"Le WebSocket n'a pas renvoyé le message envoyé en écho : "
        f"{sortie}",
    )


def test_retrait_sans_penaliser_les_sains(edge) -> None:
    edge.run("sudo docker exec pub-flux-backend-b rm -f /app/healthy")
    try:
        edge.run("sleep 2")
        echecs = 0
        for _ in range(20):
            res = _curl(edge, "api.flux.lab.test", "/lent?ms=100", max_time=3)
            if res.stdout != "200":
                echecs += 1
    finally:
        edge.run("sudo docker exec pub-flux-backend-b touch /app/healthy")

    assert echecs == 0, message(
        en=f"{echecs}/20 request(s) failed while backend b was unhealthy: "
        "it is probably still part of the rotation. Add a healthCheck to "
        "the api service.",
        fr=f"{echecs}/20 requête(s) ont échoué pendant que le backend b "
        "était malsain : il fait probablement encore partie de la "
        "rotation. Ajoutez un healthCheck au service api.",
    )


def test_post_action_sans_duplication(edge) -> None:
    edge.run("sudo docker exec pub-flux-backend-action sh -c 'echo 0 > /app/compteur'")
    edge.run("sudo docker exec pub-flux-backend-action touch /app/couper-une-fois")

    _curl(edge, "action.flux.lab.test", "/action", methode="POST", max_time=5)

    compteur = edge.run(
        "curl -s -H 'Host: action.flux.lab.test' http://127.0.0.1/compteur"
    ).stdout.strip()
    assert compteur == "1", message(
        en=f"The backend counter is {compteur!r} after a single business "
        "POST whose response was lost: a retry policy is replaying a "
        "non-idempotent action. Remove (or correctly scope) the retry "
        "middleware on the action router.",
        fr=f"Le compteur du backend vaut {compteur!r} après un seul POST "
        "métier dont la réponse a été perdue : une politique de retry "
        "rejoue une action non idempotente. Retirez (ou cadrez "
        "correctement) le middleware de retry sur le routeur action.",
    )
