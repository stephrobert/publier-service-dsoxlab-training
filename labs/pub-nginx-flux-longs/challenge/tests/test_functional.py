"""Verify WebSocket two-way traffic, SSE delivered one event at a time, gRPC
working with application errors kept distinct, and resources released.

CE QUE CHAQUE TRANSPORT EXIGE DU PROXY, ET QUI DIFFERE

Le WebSocket a besoin que la poignee de main soit TRANSMISE : sans
`Upgrade` ni `Connection`, elle n'aboutit pas. Le SSE a besoin que rien ne
soit MIS EN TAMPON : livres ensemble a la fin, les six evenements sont tous
presents et parfaitement inutilisables. Le gRPC a besoin d'HTTP/2 et de
`grpc_pass` : un proxy HTTP ordinaire ne passe pas.

LE PIEGE DU SSE EST LE PLUS SOURNOIS, parce que le test naif le rate : les
six evenements FINISSENT par arriver. Ce qui distingue un flux d'un lot,
c'est le RYTHME, donc on mesure le temps entre le premier et le dernier.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
NOM = "flux.lab.test"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def test_le_websocket_echange_dans_les_deux_sens(poste, ip_edge) -> None:
    """La poignee de main, PUIS une trame qui revient.

    Exiger seulement le 101 laisserait passer un proxy qui etablit la
    connexion et ne transporte plus rien ensuite, ce qui est exactement
    l'etat ou le defaut se diagnostique le plus mal.
    """
    sortie = poste.run(
        "python3 - <<'FIN'\n"
        "import base64, os, socket\n"
        f"cible = ('{ip_edge}', 80)\n"
        "cle = base64.b64encode(os.urandom(16)).decode()\n"
        "s = socket.create_connection(cible, timeout=15)\n"
        "s.sendall(('GET /ws HTTP/1.1\\r\\n'\n"
        f"          'Host: {NOM}\\r\\n'\n"
        "          'Upgrade: websocket\\r\\n'\n"
        "          'Connection: Upgrade\\r\\n'\n"
        "          'Sec-WebSocket-Version: 13\\r\\n'\n"
        "          f'Sec-WebSocket-Key: {cle}\\r\\n\\r\\n').encode())\n"
        "entete = s.recv(4096)\n"
        "print('POIGNEE', b'101' in entete)\n"
        "charge = b'bonjour'\n"
        "masque = os.urandom(4)\n"
        "corps = bytes(o ^ masque[i % 4] for i, o in enumerate(charge))\n"
        "s.sendall(b'\\x81' + bytes([0x80 | len(charge)]) + masque + corps)\n"
        "s.settimeout(10)\n"
        "try:\n"
        "    reponse = s.recv(4096)\n"
        "except OSError as e:\n"
        "    reponse = str(e).encode()\n"
        "print('RETOUR', reponse[2:].decode('utf-8', 'replace'))\n"
        "FIN"
    ).stdout

    assert "POIGNEE True" in sortie, message(
        en=(
            f"The WebSocket handshake did not complete ({sortie.strip()[:160]!r}). "
            "Nginx must forward the Upgrade and Connection headers, with "
            "`proxy_http_version 1.1`."
        ),
        fr=(
            f"La poignée de main WebSocket n'a pas abouti "
            f"({sortie.strip()[:160]!r}). Nginx doit transmettre les en-têtes "
            "Upgrade et Connection, avec `proxy_http_version 1.1`."
        ),
    )
    assert "echo:bonjour" in sortie, message(
        en=(
            "The handshake succeeded but nothing came back through the socket "
            f"({sortie.strip()[:200]!r}). A connection that is established and "
            "carries nothing is the hardest version of this defect to "
            "diagnose."
        ),
        fr=(
            "La poignée de main a réussi mais rien n'est revenu par la socket "
            f"({sortie.strip()[:200]!r}). Une connexion établie qui ne "
            "transporte rien est la version la plus difficile à diagnostiquer "
            "de ce défaut."
        ),
    )


def test_les_evenements_sse_arrivent_un_par_un(poste, ip_edge) -> None:
    """Le RYTHME, et non le nombre : la mise en tampon les livre tous.

    Le backend emet six evenements a une seconde d'intervalle. Si le proxy
    met en tampon, ils arrivent ensemble au bout de six secondes, et un test
    qui compterait les evenements serait vert.
    """
    debut = time.monotonic()
    premier = poste.run(
        f"curl -sN --max-time 20 -H 'Host: {NOM}' http://{ip_edge}/sse "
        "| head -c 60"
    ).stdout
    delai_premier = time.monotonic() - debut

    assert "evenement-1" in premier, message(
        en=f"No SSE event arrived at all ({premier.strip()[:120]!r}).",
        fr=f"Aucun événement SSE n'est arrivé ({premier.strip()[:120]!r}).",
    )
    assert delai_premier < 4, message(
        en=(
            f"The first event took {delai_premier:.1f} s to arrive, while the "
            "backend emits it immediately. The proxy is buffering: the six "
            "events will be delivered together at the end, all present and "
            "all useless. Turn `proxy_buffering` off on this route."
        ),
        fr=(
            f"Le premier événement a mis {delai_premier:.1f} s à arriver, alors "
            "que le backend l'émet tout de suite. Le proxy met en tampon : les "
            "six événements seront livrés ensemble à la fin, tous présents et "
            "tous inutiles. Désactivez `proxy_buffering` sur cette route."
        ),
    )


def test_grpc_fonctionne_et_distingue_une_erreur_applicative(
    poste, ip_edge
) -> None:
    """Les deux moities : l'appel qui passe, et le refus qui reste un refus.

    Un proxy mal regle transforme un refus applicatif en panne de
    transport. Le client ne sait alors plus quoi faire : on ne reessaie pas
    un argument invalide, on reessaie une indisponibilite.
    """
    ok = poste.run(
        f"python3 /usr/local/bin/client-grpc {ip_edge}:18104 bonjour"
    ).stdout.strip()
    assert ok.startswith("ok"), message(
        en=(
            f"The gRPC call did not go through: {ok!r}. gRPC needs HTTP/2 and "
            "`grpc_pass`; a plain HTTP proxy does not carry it."
        ),
        fr=(
            f"L'appel gRPC n'est pas passé : {ok!r}. gRPC exige HTTP/2 et "
            "`grpc_pass` ; un proxy HTTP ordinaire ne le transporte pas."
        ),
    )

    refus = poste.run(
        f"python3 /usr/local/bin/client-grpc {ip_edge}:18104 erreur"
    ).stdout.strip()
    assert refus.startswith("erreur"), message(
        en=(
            f"The application refusal arrived as {refus!r}. An INVALID_ARGUMENT "
            "must not reach the client as UNAVAILABLE: one is not retried, the "
            "other is, and confusing them makes every client retry a request "
            "that will never succeed."
        ),
        fr=(
            f"Le refus applicatif est arrivé sous la forme {refus!r}. Un "
            "INVALID_ARGUMENT ne doit pas parvenir au client en UNAVAILABLE : "
            "l'un ne se réessaie pas, l'autre si, et les confondre fait "
            "réessayer indéfiniment une requête qui n'aboutira jamais."
        ),
    )


def test_la_coupure_backend_libere_les_ressources(edge, poste, ip_edge) -> None:
    """Un flux long dont le backend tombe ne doit pas retenir le proxy.

    On compte les connexions etablies avant et apres : une connexion
    orpheline par client finit par epuiser le proxy, et le symptome
    apparait des semaines plus tard sous la forme « le site est lent ».
    """
    avant = edge.run(
        "ss -tn state established '( sport = :80 )' | wc -l"
    ).stdout.strip()

    # Un flux ouvert, puis le backend coupe sous lui.
    poste.run(
        f"nohup curl -sN --max-time 30 -H 'Host: {NOM}' "
        f"http://{ip_edge}/sse >/dev/null 2>&1 &"
    )
    time.sleep(2)
    edge.run("sudo systemctl restart pub-nginx-flux-backends")
    time.sleep(8)

    apres = edge.run(
        "ss -tn state established '( sport = :80 )' | wc -l"
    ).stdout.strip()

    assert avant.isdigit() and apres.isdigit(), message(
        en="Could not count the established connections.",
        fr="Impossible de compter les connexions établies.",
    )
    assert int(apres) <= int(avant) + 2, message(
        en=(
            f"Established connections went from {avant} to {apres} after the "
            "backend was cut. The proxy is holding sockets whose backend is "
            "gone: one orphan per client eventually exhausts it, and the "
            "symptom appears weeks later as « the site is slow »."
        ),
        fr=(
            f"Les connexions établies sont passées de {avant} à {apres} après "
            "la coupure du backend. Le proxy retient des sockets dont le "
            "backend a disparu : une orpheline par client finit par l'épuiser, "
            "et le symptôme apparaît des semaines plus tard sous la forme "
            "« le site est lent »."
        ),
    )
