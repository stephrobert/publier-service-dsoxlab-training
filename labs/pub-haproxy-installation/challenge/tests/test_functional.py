"""Verify the running HAProxy matches the manifest, that its HTTP and TCP
frontends really are in different modes, that neither stats nor the runtime
socket is reachable from the network, and that all of it survives a reboot.

CE QUE LE SETUP POSE : HAProxy installé, trois services sur la boucle locale,
le manifeste écrit, et une configuration SANS listener. Le service est arrêté
et non activé au démarrage.

LA MESURE QUI NE SE LAISSE PAS RACONTER

Deux contrôles de ce lab refusent de lire un fichier de configuration, et
c'est le point.

`maxconn` et `nbthread` sont lus par le socket d'administration, donc sur
l'instance vivante. Une valeur écrite dans `haproxy.cfg` et jamais chargée
n'est pas une valeur appliquée, et la différence entre les deux est
exactement ce qu'un rechargement oublié produit.

Les sockets d'écoute sont énumérés par `ss`, sur le processus réellement en
service. Un `bind` que l'on croit limité à la boucle locale et qui écoute
partout se voit là, et nulle part ailleurs : la configuration dit l'intention,
le noyau dit le fait.
"""

from __future__ import annotations

import re
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
MANIFESTE = "/opt/pub-haproxy-installation/manifeste.txt"
MARQUE = "pub-haproxy-installation service"
ECHO = "pub-haproxy-installation echo"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


@pytest.fixture(scope="module")
def ip_poste():
    return lab_host_ip(CLIENT)


def _manifeste(edge, cle: str) -> str:
    """Lit une valeur du manifeste.

    L'ancre `^` suffit à écarter les commentaires, qui commencent tous par
    `#`. Le manifeste le dit lui-même, et c'est une garantie de format, pas
    une finesse du lecteur : une phrase qui débuterait par le mot cherché
    tromperait n'importe quel lecteur de mots-clés.
    """
    valeur = edge.run(f"grep -oP '(?<=^{cle} = ).*' {MANIFESTE}").stdout.strip()
    assert valeur, message(
        en=f"The manifest {MANIFESTE} declares no `{cle}`.",
        fr=f"Le manifeste {MANIFESTE} ne déclare aucun `{cle}`.",
    )
    return valeur


def _socket_admin(edge, commande: str) -> str:
    chemin = _manifeste(edge, "socket_admin")
    return edge.run(
        f"echo '{commande}' | sudo socat -t2 stdio {chemin} 2>&1"
    ).stdout


def _page(poste, ip: str, nom: str, chemin: str = "/") -> str:
    return poste.run(
        f"curl -s --max-time 10 -H 'Host: {nom}' http://{ip}{chemin}"
    ).stdout


def _ecoutes_hors_boucle_locale(edge) -> set[int]:
    """Les ports TCP sur lesquels HAProxy écoute ailleurs que sur loopback.

    Mesuré sur le processus, pas sur le fichier : un `bind` que l'on croit
    restreint et qui écoute partout n'est visible que là.
    """
    sortie = edge.run("sudo ss -ltnpH").stdout
    ports: set[int] = set()
    for ligne in sortie.splitlines():
        if "haproxy" not in ligne:
            continue
        champs = ligne.split()
        if len(champs) < 4:
            continue
        adresse = champs[3]
        separateur = adresse.rfind(":")
        if separateur < 0:
            continue
        hote, port = adresse[:separateur], adresse[separateur + 1 :]
        if hote.startswith("127.") or hote in ("[::1]", "::1"):
            continue
        if port.isdigit():
            ports.add(int(port))
    return ports



def _attendre_retour(machine, limite_s: float = 180.0) -> bool:
    """Attend qu'une machine redemarree reponde de nouveau.

    `testinfra` LEVE quand la connexion SSH echoue, au lieu de rendre un
    resultat en echec. Une machine absente pendant son redemarrage n'est
    pourtant pas une erreur de test : c'est l'etat qu'on attend. On traite
    donc l'exception comme une reponse negative, et on reessaie.

    Mesure du 2026-10-26 : sans cette tolerance, le test echoue en 22
    secondes au lieu d'attendre, sur un `Connection refused` qui signifie
    seulement que sshd n'ecoute pas encore.
    """
    limite = time.monotonic() + limite_s
    while time.monotonic() < limite:
        try:
            resultat = machine.run("echo up")
        except Exception:  # noqa: BLE001 - toute panne de transport vaut « pas encore »
            time.sleep(5)
            continue
        if resultat.rc == 0 and "up" in resultat.stdout:
            return True
        time.sleep(5)
    return False

def test_ce_qui_tourne_suit_le_manifeste(edge) -> None:
    """La version vient du binaire exécuté, les réglages de l'instance vivante.

    On résout `/proc/<pid>/exe` au lieu de lancer `haproxy -v` : le second
    interroge le premier binaire que le `PATH` propose, qui n'est pas
    forcément celui que systemd a lancé. La question posée est « que fait
    tourner cette machine », pas « que trouverait mon shell ».
    """
    pid = edge.run("systemctl show -p MainPID --value haproxy").stdout.strip()
    assert pid and pid != "0", message(
        en="HAProxy is not running: `systemctl status haproxy` and `haproxy -c "
        "-f /etc/haproxy/haproxy.cfg` say why.",
        fr="HAProxy ne tourne pas : `systemctl status haproxy` et `haproxy -c "
        "-f /etc/haproxy/haproxy.cfg` disent pourquoi.",
    )

    binaire = edge.run(f"sudo readlink -f /proc/{pid}/exe").stdout.strip()
    assert binaire, message(
        en=f"Cannot resolve the binary of process {pid}.",
        fr=f"Impossible de résoudre le binaire du processus {pid}.",
    )

    attendue = _manifeste(edge, "version")
    reelle = edge.run(
        f"sudo {binaire} -v | head -1 | grep -oP '(?<=version )[^ ]+'"
    ).stdout.strip()
    assert reelle == attendue, message(
        en=(
            f"The running binary ({binaire}) reports version {reelle!r}, the "
            f"manifest announces {attendue!r}."
        ),
        fr=(
            f"Le binaire en service ({binaire}) annonce la version {reelle!r}, "
            f"le manifeste annonce {attendue!r}."
        ),
    )

    info = _socket_admin(edge, "show info")
    assert "Nbthread" in info, message(
        en=(
            "`show info` returned nothing usable through the runtime socket "
            f"(answer: {info.strip()[:160]!r}). The manifest asks for an "
            "administration socket, and the rest of the series needs it."
        ),
        fr=(
            "`show info` n'a rien rendu d'exploitable par le socket "
            f"d'administration (réponse : {info.strip()[:160]!r}). Le manifeste "
            "demande un socket d'administration, et la suite de la série en a "
            "besoin."
        ),
    )

    for cle, champ in (("maxconn", "Maxconn"), ("nbthread", "Nbthread")):
        voulu = _manifeste(edge, cle)
        trouve = re.search(rf"^{champ}: *(\d+)", info, re.M)
        assert trouve, message(
            en=f"`show info` does not report {champ}.",
            fr=f"`show info` ne rapporte pas {champ}.",
        )
        assert trouve.group(1) == voulu, message(
            en=(
                f"The live instance reports {champ} = {trouve.group(1)}, the "
                f"manifest asks for {voulu}. A value written in a file that was "
                "never loaded is not a value applied."
            ),
            fr=(
                f"L'instance vivante annonce {champ} = {trouve.group(1)}, le "
                f"manifeste demande {voulu}. Une valeur écrite dans un fichier "
                "qui n'a jamais été chargé n'est pas une valeur appliquée."
            ),
        )


def _recette_http(edge, poste, ip_edge: str, ip_poste: str) -> None:
    """Les deux noms atteignent leur service, et le backend voit le client."""
    for cle_nom, service in (("nom_a", "a"), ("nom_b", "b")):
        nom = _manifeste(edge, cle_nom)
        corps = _page(poste, ip_edge, nom)
        assert f"{MARQUE} {service}" in corps, message(
            en=(
                f"{nom} does not reach service {service} from the client "
                f"(answer: {corps.strip()[:160]!r})."
            ),
            fr=(
                f"{nom} n'atteint pas le service {service} depuis le client "
                f"(réponse : {corps.strip()[:160]!r})."
            ),
        )
        transmis = ""
        for ligne in corps.splitlines():
            if ligne.startswith("x-forwarded-for:"):
                transmis = ligne.split(":", 1)[1].strip()
        assert transmis and transmis != "absent", message(
            en=(
                f"Service {service} received no X-Forwarded-For. In HTTP mode "
                "the proxy is the only one that still knows the client's "
                "address: once it forwards the request, the backend sees the "
                "proxy."
            ),
            fr=(
                f"Le service {service} n'a reçu aucun X-Forwarded-For. En mode "
                "HTTP, le proxy est le seul à connaître encore l'adresse du "
                "client : une fois la requête transmise, le backend ne voit plus "
                "que le proxy."
            ),
        )
        assert ip_poste in transmis, message(
            en=(
                f"Service {service} received X-Forwarded-For {transmis!r}, which "
                f"does not carry the client address {ip_poste}. The backend is "
                "the witness here: a header the proxy declares to itself proves "
                "nothing."
            ),
            fr=(
                f"Le service {service} a reçu X-Forwarded-For {transmis!r}, qui "
                f"ne porte pas l'adresse du client {ip_poste}. C'est le backend "
                "qui témoigne : un en-tête que le proxy se déclare à lui-même ne "
                "prouve rien."
            ),
        )


def test_le_mode_http_route_les_deux_noms_et_transmet_l_adresse(
    edge, poste, ip_edge, ip_poste
) -> None:
    _recette_http(edge, poste, ip_edge, ip_poste)


def _recette_tcp(edge, poste, ip_edge: str) -> None:
    """Le relais passe les octets, le frontend HTTP refuse la même ligne."""
    port_tcp = _manifeste(edge, "port_tcp")
    jeton = f"jeton-{int(time.time())}"

    relaye = poste.run(
        f"ligne-brute {ip_edge} {port_tcp} 'PING {jeton}'"
    ).stdout.strip()
    assert relaye == f"{ECHO} PING {jeton}", message(
        en=(
            f"Port {port_tcp} did not relay the raw line (answer: {relaye!r}). "
            "Expected the line service's echo, which means a TCP relay towards "
            "it."
        ),
        fr=(
            f"Le port {port_tcp} n'a pas relayé la ligne brute (réponse : "
            f"{relaye!r}). On attend l'écho du service de lignes, donc un relais "
            "TCP vers lui."
        ),
    )

    # LE CONTRE-TEST, et il est la moitie qui compte. Une ligne de requete
    # HTTP volontairement invalide doit passer le relais, et etre refusee par
    # le frontend HTTP. Si les deux ports repondaient pareil, les deux
    # frontends sont dans le meme mode, quelles que soient les directives
    # ecrites dans le fichier.
    fausse = "GET / HTTP/9.9"
    par_le_relais = poste.run(
        f'ligne-brute {ip_edge} {port_tcp} "{fausse}"'
    ).stdout.strip()
    assert par_le_relais == f"{ECHO} {fausse}", message(
        en=(
            f"Port {port_tcp} did not relay an invalid HTTP request line "
            f"(answer: {par_le_relais!r}). A TCP relay does not read what it "
            "carries; a frontend in HTTP mode would have rejected this line."
        ),
        fr=(
            f"Le port {port_tcp} n'a pas relayé une ligne de requête HTTP "
            f"invalide (réponse : {par_le_relais!r}). Un relais TCP ne lit pas ce "
            "qu'il transporte ; un frontend en mode HTTP aurait refusé cette "
            "ligne."
        ),
    )

    par_le_http = poste.run(
        f'ligne-brute {ip_edge} 80 "{fausse}"'
    ).stdout.strip()
    # On ne juge PAS sur un code de statut. Mesure du 2026-10-26 : HAProxy
    # accepte `HTTP/9.9`, ne trouve pas d'en-tete Host, et rend 404 par le
    # backend de refus, la ou on attendait 400. Le code depend de la
    # configuration et de la version ; la propriete, elle, ne depend de rien
    # d'autre que du mode : un frontend HTTP repond EN HTTP, un relais
    # renvoie ce qu'il a transporte.
    assert par_le_http.startswith("HTTP/") and ECHO not in par_le_http, message(
        en=(
            f"Port 80 answered {par_le_http!r} to an invalid HTTP request line. "
            "A frontend in HTTP mode answers in HTTP, whatever status it "
            "picks; a relay returns what it carried. Getting the line service's "
            "echo here means both frontends are in the same mode."
        ),
        fr=(
            f"Le port 80 a répondu {par_le_http!r} à une ligne de requête HTTP "
            "invalide. Un frontend en mode HTTP répond en HTTP, quel que soit "
            "le code qu'il choisit ; un relais renvoie ce qu'il a transporté. "
            "Recevoir ici l'écho du service de lignes signifie que les deux "
            "frontends sont dans le même mode."
        ),
    )


def test_le_mode_tcp_relaie_sans_comprendre(edge, poste, ip_edge) -> None:
    _recette_tcp(edge, poste, ip_edge)


def _recette_exposition(edge, poste, ip_edge: str) -> None:
    """Rien hors boucle locale que les deux ports publiés, et l'état répond."""
    port_stats = _manifeste(edge, "port_stats")
    port_tcp = int(_manifeste(edge, "port_tcp"))

    ports = _ecoutes_hors_boucle_locale(edge)
    attendus = {80, port_tcp}
    de_trop = ports - attendus
    assert not de_trop, message(
        en=(
            f"HAProxy listens outside the loopback on {sorted(de_trop)}, beyond "
            f"the published {sorted(attendus)}. The stats page and the runtime "
            "socket must stay on the machine. This is measured on the process, "
            "not in the file: `bind` says the intent, the kernel says the fact."
        ),
        fr=(
            f"HAProxy écoute hors boucle locale sur {sorted(de_trop)}, en plus "
            f"des {sorted(attendus)} publiés. La page d'état et le socket "
            "d'administration doivent rester sur la machine. C'est mesuré sur le "
            "processus, pas dans le fichier : `bind` dit l'intention, le noyau "
            "dit le fait."
        ),
    )
    assert attendus <= ports, message(
        en=(
            f"HAProxy does not listen outside the loopback on all of "
            f"{sorted(attendus)} (seen: {sorted(ports)}). The published ports "
            "must be reachable from the client."
        ),
        fr=(
            f"HAProxy n'écoute pas hors boucle locale sur tous les "
            f"{sorted(attendus)} (vus : {sorted(ports)}). Les ports publiés "
            "doivent être joignables depuis le client."
        ),
    )

    depuis_le_client = poste.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"http://{ip_edge}:{port_stats}/"
    ).stdout.strip()
    assert depuis_le_client == "000", message(
        en=(
            f"The stats page answered {depuis_le_client} from the client on port "
            f"{port_stats}. A status page tells which backends exist, which are "
            "down and how much traffic they take: it belongs on the machine."
        ),
        fr=(
            f"La page d'état a répondu {depuis_le_client} depuis le client sur le "
            f"port {port_stats}. Une page d'état dit quels backends existent, "
            "lesquels sont tombés et combien de trafic ils prennent : elle reste "
            "sur la machine."
        ),
    )

    # LES DEUX MOITIES. « Pas public » se satisfait trivialement en n'ayant
    # rien du tout. On exige donc aussi que les deux outils existent et
    # repondent depuis la machine : c'est ce qui distingue une exposition
    # maitrisee d'une absence.
    local = edge.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
        f"http://127.0.0.1:{port_stats}/"
    ).stdout.strip()
    assert local.startswith(("200", "401")), message(
        en=(
            f"The stats page answers {local} on the machine's loopback. It must "
            "exist and answer there: not public is not the same as not there."
        ),
        fr=(
            f"La page d'état répond {local} sur la boucle locale de la machine. "
            "Elle doit exister et répondre : « pas publique » n'est pas « pas "
            "là »."
        ),
    )

    chemin = _manifeste(edge, "socket_admin")
    sortie = edge.run(f"sudo stat -c '%F %a' {chemin}").stdout.strip()
    assert sortie.startswith("socket"), message(
        en=(
            f"{chemin} is not a UNIX socket ({sortie!r}). An administration "
            "socket exposed over TCP is a remote shell on the proxy: it can "
            "disable servers and read the configuration."
        ),
        fr=(
            f"{chemin} n'est pas un socket UNIX ({sortie!r}). Un socket "
            "d'administration exposé en TCP est un interpréteur à distance sur "
            "le proxy : il peut désactiver des serveurs et lire la "
            "configuration."
        ),
    )
    droits = sortie.split()[-1]
    assert int(droits, 8) & 0o007 == 0, message(
        en=(
            f"{chemin} is mode {droits}: anyone with an account on the machine "
            "can drive the proxy. Keep it to its owner and its group."
        ),
        fr=(
            f"{chemin} est en mode {droits} : n'importe quel compte de la machine "
            "peut piloter le proxy. Réservez-le à son propriétaire et à son "
            "groupe."
        ),
    )


def test_l_etat_et_l_administration_ne_sont_pas_publics(edge, poste, ip_edge) -> None:
    """CRITIQUE : ce qui doit rester sur la machine y reste, et existe."""
    _recette_exposition(edge, poste, ip_edge)


def test_tout_revient_apres_un_redemarrage(edge, poste, ip_edge, ip_poste) -> None:
    """CRITIQUE, et dernier : il coupe la machine, et rejoue la recette entière.

    Rejouer les trois contrôles précédents plutôt qu'une seule requête est ce
    qui fait la différence : une configuration appliquée à la main revient
    souvent « à moitié » après un redémarrage, et c'est le relais TCP ou la
    restriction d'écoute qui manque, pas la page d'accueil.
    """
    _recette_http(edge, poste, ip_edge, ip_poste)

    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)

    revenu = _attendre_retour(edge, 180)
    assert revenu, message(
        en="edge.lab did not come back online within 180s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180 s après le redémarrage.",
    )

    # Le service peut mettre quelques secondes a reprendre : on attend, au
    # lieu de conclure sur la premiere tentative.
    limite = time.monotonic() + 120
    while time.monotonic() < limite:
        nom = _manifeste(edge, "nom_a")
        if f"{MARQUE} a" in _page(poste, ip_edge, nom):
            break
        time.sleep(5)
    else:
        pytest.fail(
            message(
                en=(
                    "After the reboot, HAProxy does not answer again by itself. "
                    "It was started, not installed: enable it so systemd brings "
                    "it back, and make sure its configuration is on disk rather "
                    "than applied by hand."
                ),
                fr=(
                    "Après le redémarrage, HAProxy ne répond pas de lui-même. Il "
                    "avait été lancé, pas installé : activez-le pour que systemd "
                    "le ramène, et vérifiez que sa configuration est sur le "
                    "disque plutôt qu'appliquée à la main."
                ),
            )
        )

    _recette_http(edge, poste, ip_edge, ip_poste)
    _recette_tcp(edge, poste, ip_edge)
    _recette_exposition(edge, poste, ip_edge)
