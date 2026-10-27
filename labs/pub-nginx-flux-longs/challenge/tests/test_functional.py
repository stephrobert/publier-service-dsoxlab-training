"""Verify WebSocket two-way traffic, SSE delivered one event at a time, gRPC
working with application errors kept distinct, and a silent stream surviving
the proxy read timeout.

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
# Au-dela des 10 s du reglage de depart, en deca de ce qu'un
# apprenant attendrait sans s'inquieter.
SILENCE = 15


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
        # La LIGNE DE STATUT, et non « 101 » quelque part dans l'en-tete.
        # Mesure du 2026-10-26 : ce test passait sur l'etat de depart, qui ne
        # transmet pourtant ni Upgrade ni Connection. La suite « 101 » se
        # trouve ailleurs qu'en tete de reponse, a commencer par le port du
        # backend (18101) qu'une page d'erreur peut citer. Un test qui
        # cherche trois caracteres n'importe ou ne mesure pas un protocole.
        "print('POIGNEE', entete.split(b'\\r\\n')[0].startswith(b'HTTP/1.1 101'))\n"
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
            "Nginx must forward the Upgrade and Connection headers: they are "
            "hop-by-hop headers, so it drops them unless the location sets "
            "them again. `proxy_http_version` is not the cause here, 1.1 has "
            "been the default since nginx 1.29.7."
        ),
        fr=(
            f"La poignée de main WebSocket n'a pas abouti "
            f"({sortie.strip()[:160]!r}). Nginx doit transmettre les en-têtes "
            "Upgrade et Connection : ce sont des en-têtes de saut, il les "
            "retire donc si le location ne les repose pas. "
            "`proxy_http_version` n'est pas la cause ici, 1.1 est le défaut "
            "depuis nginx 1.29.7."
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


def test_un_flux_silencieux_survit_au_delai_de_lecture(poste, ip_edge) -> None:
    """Le SILENCE, et non le trafic : c'est lui qui coupe.

    `proxy_read_timeout` compte le temps ecoule ENTRE DEUX LECTURES du
    backend. Un flux bavard ne le declenche donc jamais, et le defaut reste
    invisible tant qu'on ne se tait pas : c'est ce qui le fait decouvrir en
    production, sur la conversation qui n'avait rien a dire pendant une
    minute. Le banc se tait quinze secondes, la ou le reglage de depart
    coupe a dix.

    Ce test ne double pas le premier. Celui-la demande que la poignee de
    main soit transmise ; celui-ci demande qu'elle SURVIVE. Une recette qui
    transmet `Upgrade` en laissant le delai a dix secondes passe le premier
    et echoue ici, ce qui est exactement la distinction a enseigner.
    """
    sortie = poste.run(
        "python3 - <<'FIN'\n"
        "import base64, os, socket, time\n"
        f"cible = ('{ip_edge}', 80)\n"
        "cle = base64.b64encode(os.urandom(16)).decode()\n"
        # Le delai de la socket couvre le silence, sinon c'est le CLIENT qui
        # abandonne, et le test mesure alors sa propre impatience.
        "s = socket.create_connection(cible, timeout=40)\n"
        "s.sendall(('GET /ws HTTP/1.1\\r\\n'\n"
        f"          'Host: {NOM}\\r\\n'\n"
        "          'Upgrade: websocket\\r\\n'\n"
        "          'Connection: Upgrade\\r\\n'\n"
        "          'Sec-WebSocket-Version: 13\\r\\n'\n"
        "          f'Sec-WebSocket-Key: {cle}\\r\\n\\r\\n').encode())\n"
        "entete = s.recv(4096)\n"
        "print('POIGNEE', entete.split(b'\\r\\n')[0].startswith(b'HTTP/1.1 101'))\n"
        f"time.sleep({SILENCE})\n"
        "charge = b'apres-le-silence'\n"
        "masque = os.urandom(4)\n"
        "corps = bytes(o ^ masque[i % 4] for i, o in enumerate(charge))\n"
        "try:\n"
        "    s.sendall(b'\\x81' + bytes([0x80 | len(charge)]) + masque + corps)\n"
        "    s.settimeout(10)\n"
        "    reponse = s.recv(4096)\n"
        "except OSError as e:\n"
        "    reponse = str(e).encode()\n"
        # Une socket fermee par le proxy rend b'' sans lever : le dire
        # explicitement, sinon le message final ne montre qu'une chaine vide
        # dont personne ne sait si elle vient d'un timeout ou d'une coupure.
        "print('RETOUR', reponse[2:].decode('utf-8', 'replace')\n"
        "      if reponse else 'connexion fermee par le proxy')\n"
        "FIN"
    ).stdout

    assert "POIGNEE True" in sortie, message(
        en=(
            f"The handshake did not complete ({sortie.strip()[:160]!r}), so "
            "the read timeout could not be measured. Fix the Upgrade and "
            "Connection headers first."
        ),
        fr=(
            f"La poignée de main n'a pas abouti ({sortie.strip()[:160]!r}), "
            "le délai de lecture n'a donc pas pu être mesuré. Corrigez "
            "d'abord les en-têtes Upgrade et Connection."
        ),
    )
    assert "echo:apres-le-silence" in sortie, message(
        en=(
            f"The connection did not survive {SILENCE} s of silence "
            f"({sortie.strip()[:200]!r}). `proxy_read_timeout` counts the time "
            "BETWEEN TWO READS from the backend, not the lifetime of the "
            "stream: a chatty stream never triggers it, and the defect only "
            "shows up on the conversation that had nothing to say for a "
            "minute. Raise it on the routes that carry long streams."
        ),
        fr=(
            f"La connexion n'a pas survécu à {SILENCE} s de silence "
            f"({sortie.strip()[:200]!r}). `proxy_read_timeout` compte le temps "
            "écoulé ENTRE DEUX LECTURES du backend, et non la durée du flux : "
            "un flux bavard ne le déclenche jamais, et le défaut ne se montre "
            "que sur la conversation qui n'avait rien à dire pendant une "
            "minute. Allongez-le sur les routes qui portent des flux longs."
        ),
    )
