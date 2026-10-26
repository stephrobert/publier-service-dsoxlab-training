"""Verify that the backend's identity is checked and the impostor refused,
that a valid client identity is told apart from an absence and from another
authority, that a client cannot choose its own address by header or by PROXY
protocol, and that the authorised route carries protocol and identity to the
application.

CE QUE LE SETUP POSE : quatre autorites, un backend legitime, un IMPOSTEUR
qui porte le meme nom et sert le meme marqueur, et un HAProxy ou tout repond.

POURQUOI LE BACKEND RENVOIE CE QU'IL A RECU

Les controles 3 et 4 lisent les en-tetes que le BACKEND a vus, et non ceux
que le proxy dit avoir envoyes. C'est la seule facon de mesurer la confiance :
un proxy qui se declare a lui-meme une adresse de client ne prouve rien, et
un `http-request set-header` ecrit dans la configuration ne dit pas ce qui
est arrive au bout de la chaine. Le temoin est l'application.

POURQUOI LE CANARI RESTE DANS LA CONFIGURATION

`/api-usurpe/` doit passer en 502 et y rester. Son refus est la preuve que la
verification du backend est stricte. Un apprenant qui retire cette route
rendrait le controle vert sans avoir rien verifie : c'est pour cela que le
test exige SA PRESENCE en meme temps que son refus.
"""

from __future__ import annotations

import uuid

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-confiance/recette.txt"
MARQUE = "pub-haproxy-confiance backend"


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


def _valeur(edge, cle: str) -> str:
    valeur = edge.run(f"grep -oP '(?<=^{cle} = ).*' {RECETTE}").stdout.strip()
    assert valeur, message(
        en=f"The recipe {RECETTE} declares no `{cle}`.",
        fr=f"La recette {RECETTE} ne déclare aucun `{cle}`.",
    )
    return valeur


@pytest.fixture(scope="module")
def recette(edge) -> dict[str, str]:
    cles = (
        "nom_service",
        "port_public",
        "ca_service",
        "nom_backend",
        "ca_backend",
        "ca_clients",
        "client_valide",
        "client_etranger",
        "cn_attendu",
        "route_publique",
        "route_privee",
        "route_canari",
        "port_interne",
        "adresse_declaree",
        "source_approuvee",
    )
    return {cle: _valeur(edge, cle) for cle in cles}


def _demander(edge, recette, chemin: str, identite: str | None = None):
    """Une requête depuis la machine, avec vérification STRICTE du service.

    `--cacert` et non `-k` : la validation de ce lab porte sur la confiance,
    et une mesure qui désactiverait la vérification pour se simplifier la vie
    mesurerait autre chose.
    """
    nom = recette["nom_service"]
    port = recette["port_public"]
    cert = f"--cert {identite}" if identite else ""
    sortie = edge.run(
        f"curl -sS --cacert {recette['ca_service']} {cert} "
        f"--resolve {nom}:{port}:127.0.0.1 "
        f"-o /tmp/corps-confiance -w '%{{http_code}}' --max-time 15 "
        f"https://{nom}:{port}{chemin} 2>&1"
    )
    corps = edge.run("cat /tmp/corps-confiance 2>/dev/null").stdout
    return sortie.stdout.strip(), corps


def _entetes_vues(corps: str) -> dict[str, str]:
    """Ce que le BACKEND dit avoir reçu."""
    vues: dict[str, str] = {}
    for ligne in corps.splitlines():
        if ":" in ligne:
            cle, valeur = ligne.split(":", 1)
            vues[cle.strip().lower()] = valeur.strip()
    return vues


def test_l_identite_du_backend_est_verifiee_et_l_imposteur_refuse(
    edge, recette
) -> None:
    """CRITIQUE : le canari refuse, la route légitime sert, et pas de verify none."""
    statut, corps = _demander(
        edge, recette, recette["route_publique"], recette["client_valide"]
    )
    assert statut == "200" and MARQUE in corps, message(
        en=(
            f"The public route answered {statut} and did not reach the backend "
            f"({corps.strip()[:160]!r}). Refusing everything is not verifying: "
            "the legitimate backend must keep answering."
        ),
        fr=(
            f"La route publique a répondu {statut} et n'a pas atteint le backend "
            f"({corps.strip()[:160]!r}). Refuser tout n'est pas vérifier : le "
            "backend légitime doit continuer de répondre."
        ),
    )
    vues = _entetes_vues(corps)
    assert vues.get("origine") == "legitime", message(
        en=f"The public route reached {vues.get('origine')!r}, expected legitime.",
        fr=f"La route publique a atteint {vues.get('origine')!r}, on attend legitime.",
    )

    # LA ROUTE CANARI EXISTE ENCORE, et c'est exige en meme temps que son
    # refus : la retirer rendrait le controle vert sans rien avoir verifie.
    configuration = edge.run("sudo haproxy -c -f /etc/haproxy/haproxy.cfg -V 2>&1")
    presente = edge.run(
        f"grep -c '{recette['route_canari']}' /etc/haproxy/haproxy.cfg"
    ).stdout.strip()
    assert presente not in ("", "0"), message(
        en=(
            f"The canary route {recette['route_canari']} has disappeared from "
            "the configuration. Its refusal is what proves backend verification "
            "is strict: removing it removes the proof, it does not satisfy the "
            "check."
        ),
        fr=(
            f"La route canari {recette['route_canari']} a disparu de la "
            "configuration. Son refus est ce qui prouve que la vérification du "
            "backend est stricte : la retirer retire la preuve, elle ne satisfait "
            "pas le contrôle."
        ),
    )

    statut, corps = _demander(
        edge, recette, recette["route_canari"], recette["client_valide"]
    )
    # 502 OU 503, et non 502 seul : si une sonde de sante est declaree sur ce
    # serveur, elle echoue elle aussi sur la verification, le serveur est
    # marque indisponible, et HAProxy rend 503 au lieu de 502. Les deux codes
    # disent la meme chose, la seule qui compte ici : l'imposteur n'a pas ete
    # servi. Exiger 502 seul interdirait de declarer une sonde, ce que la
    # recette ne demande pas.
    assert statut in ("502", "503"), message(
        en=(
            f"The canary {recette['route_canari']} answered {statut}, expected "
            f"502 or 503. It leads to a backend whose certificate is signed by a "
            f"foreign authority and which carries the same name "
            f"({recette['nom_backend']}) as the legitimate one. It serves the "
            f"same marker, so its answer is indistinguishable from a success: "
            f"only the authority tells them apart. Body: {corps.strip()[:160]!r}"
        ),
        fr=(
            f"Le canari {recette['route_canari']} a répondu {statut}, on attend "
            "502 ou 503. Il mène à un backend dont le certificat est signé par une "
            f"autorité étrangère et qui porte le même nom "
            f"({recette['nom_backend']}) que le légitime. Il sert le même "
            "marqueur, donc sa réponse est indiscernable d'un succès : seule "
            f"l'autorité les distingue. Corps : {corps.strip()[:160]!r}"
        ),
    )

    # Seconde formulation de la MEME exigence, et la recette la nomme :
    # « sans verify none ». Elle porte sur une declaration, donc elle se lit
    # dans la declaration.
    sans_verification = edge.run(
        "grep -c 'verify none' /etc/haproxy/haproxy.cfg"
    ).stdout.strip()
    assert sans_verification in ("", "0"), message(
        en=(
            f"`verify none` still appears {sans_verification} time(s) in the "
            "configuration. Encrypting a link without looking at who is at the "
            "other end protects against a passive listener and against nothing "
            f"else. Configuration check said: {configuration.stdout.strip()[:120]!r}"
        ),
        fr=(
            f"`verify none` apparaît encore {sans_verification} fois dans la "
            "configuration. Chiffrer une liaison sans regarder qui est à l'autre "
            "bout protège d'une écoute passive, et de rien d'autre. Le contrôle "
            f"de configuration a dit : {configuration.stdout.strip()[:120]!r}"
        ),
    )


def test_une_identite_cliente_valide_est_distinguee_des_deux_autres(
    edge, recette
) -> None:
    """CRITIQUE : les trois cas, et la route publique qui reste ouverte."""
    statut, corps = _demander(edge, recette, recette["route_publique"])
    assert statut == "200" and MARQUE in corps, message(
        en=(
            f"The public route answered {statut} without a client certificate. "
            "The recipe asks for route authorisation, not a gate: what is public "
            "stays public."
        ),
        fr=(
            f"La route publique a répondu {statut} sans certificat client. La "
            "recette demande une autorisation de route, pas un portail : ce qui "
            "est public reste public."
        ),
    )

    statut, _corps = _demander(edge, recette, recette["route_privee"])
    assert statut == "403", message(
        en=(
            f"The private route answered {statut} with no client identity at "
            "all, expected 403."
        ),
        fr=(
            f"La route privée a répondu {statut} sans aucune identité cliente, "
            "on attend 403."
        ),
    )

    statut, _corps = _demander(
        edge, recette, recette["route_privee"], recette["client_etranger"]
    )
    assert statut != "200", message(
        en=(
            f"The private route answered {statut} with a certificate signed by a "
            "foreign authority. An identity is not a certificate: it is a "
            "certificate SIGNED BY AN AUTHORITY YOU TRUST. A refusal here may be "
            "a 403 or a refused handshake; being served is the only wrong "
            "outcome."
        ),
        fr=(
            f"La route privée a répondu {statut} avec un certificat signé par une "
            "autorité étrangère. Une identité n'est pas un certificat : c'est un "
            "certificat SIGNÉ PAR UNE AUTORITÉ EN LAQUELLE ON A CONFIANCE. Un "
            "refus ici peut être un 403 ou une poignée de main refusée ; être "
            "servi est le seul résultat faux."
        ),
    )

    statut, corps = _demander(
        edge, recette, recette["route_privee"], recette["client_valide"]
    )
    assert statut == "200" and MARQUE in corps, message(
        en=(
            f"The private route answered {statut} with the identity the "
            f"clients' authority signed ({corps.strip()[:160]!r}). Refusing "
            "everything is not authorising."
        ),
        fr=(
            f"La route privée a répondu {statut} avec l'identité que l'autorité "
            f"des clients a signée ({corps.strip()[:160]!r}). Refuser tout n'est "
            "pas autoriser."
        ),
    )


def test_un_client_ne_peut_pas_choisir_son_adresse(
    edge, poste, recette, ip_edge, ip_poste
) -> None:
    """CRITIQUE : les deux chemins d'usurpation, et la capacité qu'on garde."""
    menteuse = "1.2.3.4"
    # `-k` ici, et seulement ici : la mesure porte sur le traitement de
    # l'en-tete, pas sur l'identite du service, et la racine de l'autorite
    # n'est pas sur le client. Le dire est plus honnete que de la transferer
    # pour faire joli.
    corps = poste.run(
        f"curl -sk --max-time 15 -H 'X-Forwarded-For: {menteuse}' "
        f"https://{ip_edge}:{recette['port_public']}{recette['route_publique']}"
    ).stdout
    vues = _entetes_vues(corps)
    transmis = vues.get("x-forwarded-for", "")
    assert MARQUE in corps, message(
        en=f"The client did not reach the backend ({corps.strip()[:160]!r}).",
        fr=f"Le client n'a pas atteint le backend ({corps.strip()[:160]!r}).",
    )
    assert menteuse not in transmis, message(
        en=(
            f"The application received X-Forwarded-For {transmis!r}, which "
            f"carries the address the client chose ({menteuse}). "
            "`option forwardfor` APPENDS to the received header: the client's "
            "value arrives first, and an application almost always reads the "
            "first. The incoming header has to be replaced, not extended."
        ),
        fr=(
            f"L'application a reçu X-Forwarded-For {transmis!r}, qui porte "
            f"l'adresse que le client a choisie ({menteuse}). "
            "`option forwardfor` AJOUTE à l'en-tête reçu : la valeur du client "
            "arrive en premier, et une application lit presque toujours la "
            "première. L'en-tête entrant doit être remplacé, pas complété."
        ),
    )
    assert ip_poste in transmis, message(
        en=(
            f"The application received X-Forwarded-For {transmis!r}, which does "
            f"not carry the client's real address {ip_poste}. Discarding the "
            "forged value is half the job; the other half is stating the one "
            "the proxy actually observed."
        ),
        fr=(
            f"L'application a reçu X-Forwarded-For {transmis!r}, qui ne porte pas "
            f"l'adresse réelle du client {ip_poste}. Jeter la valeur usurpée est "
            "une moitié du travail ; l'autre est de dire celle que le proxy a "
            "réellement constatée."
        ),
    )

    depuis_le_reseau = poste.run(
        f"proxy-protocole {ip_edge} {recette['port_interne']} "
        f"{recette['adresse_declaree']} {recette['route_publique']}"
    ).stdout
    assert MARQUE not in depuis_le_reseau, message(
        en=(
            f"The listener on {recette['port_interne']} served a client that "
            "declared its own address with a PROXY header, from the network. "
            "Trusting the PROXY protocol means trusting whoever can reach that "
            "port: it belongs to the approved source and to nobody else. "
            f"Answer: {depuis_le_reseau.strip()[:160]!r}"
        ),
        fr=(
            f"L'écoute sur {recette['port_interne']} a servi un client qui "
            "déclarait sa propre adresse par un en-tête PROXY, depuis le réseau. "
            "Faire confiance au protocole PROXY revient à faire confiance à "
            "quiconque atteint ce port : il appartient à la source approuvée, et "
            f"à personne d'autre. Réponse : {depuis_le_reseau.strip()[:160]!r}"
        ),
    )

    # LA MOITIE QUI COMPTE. Sans elle, le controle se satisferait de
    # supprimer l'ecoute, et la configuration aurait perdu une capacite au
    # lieu de gagner un controle.
    depuis_la_source = edge.run(
        f"proxy-protocole {recette['source_approuvee']} "
        f"{recette['port_interne']} {recette['adresse_declaree']} "
        f"{recette['route_publique']}"
    ).stdout
    vues = _entetes_vues(depuis_la_source)
    assert MARQUE in depuis_la_source, message(
        en=(
            f"The approved source {recette['source_approuvee']} can no longer "
            f"reach the listener on {recette['port_interne']} "
            f"({depuis_la_source.strip()[:160]!r}). The check is not satisfied by "
            "deleting what it watches: the trusted hop must keep working."
        ),
        fr=(
            f"La source approuvée {recette['source_approuvee']} n'atteint plus "
            f"l'écoute sur {recette['port_interne']} "
            f"({depuis_la_source.strip()[:160]!r}). Le contrôle ne se satisfait "
            "pas en supprimant ce qu'il surveille : le saut approuvé doit "
            "continuer de fonctionner."
        ),
    )
    assert recette["adresse_declaree"] in vues.get("x-forwarded-for", ""), message(
        en=(
            f"The application received X-Forwarded-For "
            f"{vues.get('x-forwarded-for')!r} from the approved source, which "
            f"declared {recette['adresse_declaree']}. An approved hop is "
            "believed, otherwise the real client's address is lost at the first "
            "proxy."
        ),
        fr=(
            f"L'application a reçu X-Forwarded-For "
            f"{vues.get('x-forwarded-for')!r} depuis la source approuvée, qui "
            f"déclarait {recette['adresse_declaree']}. Un saut approuvé est cru, "
            "sinon l'adresse du vrai client est perdue au premier proxy."
        ),
    )


def test_la_route_autorisee_conserve_protocole_et_identite(edge, recette) -> None:
    """Ce que le backend a vu, et non ce que la configuration dit envoyer."""
    jeton = uuid.uuid4().hex[:10]
    statut, corps = _demander(
        edge,
        recette,
        f"{recette['route_privee']}?jeton={jeton}",
        recette["client_valide"],
    )
    assert statut == "200", message(
        en=f"The authorised route answered {statut} with a valid identity.",
        fr=f"La route autorisée a répondu {statut} avec une identité valide.",
    )
    vues = _entetes_vues(corps)

    assert jeton in vues.get("chemin", ""), message(
        en=(
            f"The backend saw path {vues.get('chemin')!r}, which does not carry "
            f"the token {jeton} of this measurement."
        ),
        fr=(
            f"Le backend a vu le chemin {vues.get('chemin')!r}, qui ne porte pas "
            f"le jeton {jeton} de cette mesure."
        ),
    )

    assert vues.get("x-forwarded-proto") == "https", message(
        en=(
            f"The backend received X-Forwarded-Proto "
            f"{vues.get('x-forwarded-proto')!r}, expected https. The link from "
            "the proxy to the backend is a second link: the application cannot "
            "tell what the client used unless it is told."
        ),
        fr=(
            f"Le backend a reçu X-Forwarded-Proto "
            f"{vues.get('x-forwarded-proto')!r}, on attend https. La liaison du "
            "proxy au backend est une seconde liaison : l'application ne peut pas "
            "savoir ce que le client a employé si on ne le lui dit pas."
        ),
    )

    dn = vues.get("x-client-dn", "absent")
    assert recette["cn_attendu"] in dn, message(
        en=(
            f"The backend received X-Client-DN {dn!r}, which does not carry "
            f"{recette['cn_attendu']}. The proxy is the only one that saw the "
            "client certificate: if it does not pass on the verified identity, "
            "the application cannot distinguish an authorised client from the "
            "proxy itself."
        ),
        fr=(
            f"Le backend a reçu X-Client-DN {dn!r}, qui ne porte pas "
            f"{recette['cn_attendu']}. Le proxy est le seul à avoir vu le "
            "certificat client : s'il ne transmet pas l'identité vérifiée, "
            "l'application ne peut pas distinguer un client autorisé du proxy "
            "lui-même."
        ),
    )
