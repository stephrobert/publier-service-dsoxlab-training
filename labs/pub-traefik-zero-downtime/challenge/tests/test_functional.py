"""Verify a weighted rollout to a candidate backend, an automatic rollback
driven by a real health check, an honest and proven failure-domain
declaration, and a certificate rotation tool safe under concurrency.

Each test restores the state it mutates before returning: the module's
tests, and the whole suite, must remain replayable without a reset
in between.
"""

from __future__ import annotations

import re
import time

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
WORK = "/opt/pub-zds"
OUTIL = f"{WORK}/outils/tourner-certificat.sh"
TLS = f"{WORK}/tls"
ECHANTILLON = 40


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def client():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def ports(edge) -> dict[str, int]:
    brut = edge.run(f"cat {WORK}/ports.env").stdout
    trouves = {m.group(1): int(m.group(2)) for m in re.finditer(r"(ENTREE_[AB])=(\d+)", brut)}
    assert set(trouves) == {"ENTREE_A", "ENTREE_B"}, message(
        en=f"{WORK}/ports.env is missing the lab's entry point ports.",
        fr=f"{WORK}/ports.env n'a pas les ports des points d'entrée du lab.",
    )
    return trouves


@pytest.fixture(scope="module")
def adresse(edge) -> str:
    iface = edge.run("ip -4 route show default | awk '{print $5; exit}'").stdout.strip()
    ip = edge.run(
        f"ip -4 -o addr show dev {iface} scope global | awk '{{print $4}}' | cut -d/ -f1 | head -1"
    ).stdout.strip()
    assert ip, message(en="No address found on edge.lab.", fr="Aucune adresse trouvée sur edge.lab.")
    return ip


def _requete(hote, host_tete: str, ip: str, port: int) -> tuple[str, str]:
    """(code HTTP, corps) pour une requête HTTPS directe, nom et IP forcés."""
    res = hote.run(
        f"curl -k -s --max-time 4 -w '\\n%{{http_code}}' "
        f"--resolve {host_tete}:{port}:{ip} https://{host_tete}:{port}/"
    )
    lignes = res.stdout.rsplit("\n", 1)
    corps = lignes[0] if len(lignes) == 2 else ""
    code = lignes[1] if len(lignes) == 2 else ""
    return code, corps


def _repartition(edge, port: int, n: int = ECHANTILLON) -> dict[str, int]:
    """Sonde n requêtes réelles sur un point d'entrée et compte les versions."""
    compte = {"v1": 0, "v2": 0, "erreur": 0}
    for _ in range(n):
        code, corps = _requete(edge, "zds.lab.test", "127.0.0.1", port)
        if code != "200":
            compte["erreur"] += 1
        elif "version=v1" in corps:
            compte["v1"] += 1
        elif "version=v2" in corps:
            compte["v2"] += 1
        else:
            compte["erreur"] += 1
    return compte


def test_bascule_repartit_reellement_le_trafic_avec_erreurs_bornees(edge, ports) -> None:
    repartition = _repartition(edge, ports["ENTREE_A"])
    assert repartition["erreur"] <= 2, message(
        en=f"Too many failed requests while sampling traffic ({repartition}). "
        "A rollout must keep a bounded error rate.",
        fr=f"Trop de requêtes en échec en échantillonnant le trafic "
        f"({repartition}). Une bascule doit garder un taux d'erreur borné.",
    )
    assert repartition["v1"] >= 5 and repartition["v2"] >= 5, message(
        en=f"Traffic is not actually split between v1 and v2 ({repartition}). "
        "The 'app' service must spread traffic across both versions, as "
        "two weighted servers of a single load-balanced service, "
        "not a single hard-coded backend.",
        fr=f"Le trafic n'est pas réellement réparti entre v1 et v2 "
        f"({repartition}). Le service « app » doit répartir le trafic sur "
        "les deux versions, sous la forme de deux serveurs pondérés d'un "
        "même service réparti, pas un backend unique "
        "câblé en dur.",
    )


def test_rollback_retire_une_version_malsaine_et_la_restaure(edge, ports) -> None:
    port = ports["ENTREE_A"]
    edge.run("docker exec pub-zds-app-v2 test -f /app/healthy || docker exec pub-zds-app-v2 touch /app/healthy")
    try:
        edge.run("docker exec pub-zds-app-v2 rm -f /app/healthy")
        malade = None
        for _ in range(15):
            malade = _repartition(edge, port, n=20)
            if malade["v2"] == 0 and malade["erreur"] == 0:
                break
            time.sleep(1)
        assert malade is not None and malade["v2"] == 0 and malade["erreur"] == 0, message(
            en=f"Marking v2 unhealthy must remove it from rotation within a "
            f"few seconds, with no request failing in the meantime (observed: "
            f"{malade}). Add a loadBalancer.healthCheck to the service "
            f"carrying both servers.",
            fr=f"Marquer v2 malsaine doit la retirer de la rotation en "
            f"quelques secondes, sans qu'aucune requête n'échoue entretemps "
            f"(observé : {malade}). Ajoutez un loadBalancer.healthCheck "
            "au service qui porte les deux serveurs.",
        )
    finally:
        edge.run("docker exec pub-zds-app-v2 touch /app/healthy")
        retabli = None
        for _ in range(15):
            retabli = _repartition(edge, port, n=20)
            if retabli["v2"] > 0:
                break
            time.sleep(1)
        assert retabli is not None and retabli["v2"] > 0, message(
            en="v2 was restored healthy but never received traffic again: "
            "the health check must also bring a recovered backend back.",
            fr="v2 a été restaurée saine mais n'a plus jamais reçu de "
            "trafic : la sonde de santé doit aussi réintégrer un backend "
            "rétabli.",
        )


def test_domaine_de_panne_honnete_et_verifie(edge, client, ports, adresse) -> None:
    port_a = ports["ENTREE_A"]
    port_b = ports["ENTREE_B"]

    fichier = edge.file("/home/student/domaine-de-panne.yaml")
    assert fichier.exists, message(
        en="/home/student/domaine-de-panne.yaml is missing.",
        fr="/home/student/domaine-de-panne.yaml est absent.",
    )
    try:
        declare = yaml.safe_load(fichier.content_string) or {}
    except yaml.YAMLError as erreur:
        pytest.fail(message(
            en=f"/home/student/domaine-de-panne.yaml is not valid YAML: {erreur}",
            fr=f"/home/student/domaine-de-panne.yaml n'est pas un YAML valide : {erreur}",
        ))

    # --- Perte d'un seul processus : l'autre point d'entrée doit survivre. ---
    edge.run("docker stop pub-zds-entry-a")
    try:
        code_a, _ = _requete(client, "zds.lab.test", adresse, port_a)
        code_b, _ = _requete(client, "zds.lab.test", adresse, port_b)
        processus_survit = code_a != "200" and code_b == "200"
    finally:
        edge.run("docker start pub-zds-entry-a")
        for _ in range(20):
            code, _ = _requete(edge, "zds.lab.test", "127.0.0.1", port_a)
            if code == "200":
                break
            time.sleep(1)

    assert processus_survit, message(
        en=f"Stopping pub-zds-entry-a must leave pub-zds-entry-b answering "
        f"(observed entry-a={code_a!r}, entry-b={code_b!r}).",
        fr=f"Arrêter pub-zds-entry-a doit laisser pub-zds-entry-b répondre "
        f"(observé entry-a={code_a!r}, entry-b={code_b!r}).",
    )

    # --- Perte de l'hôte unique qui porte les deux points d'entrée : les
    # deux DOIVENT devenir injoignables, puisqu'ils partagent la même VM.
    # Bloquer dans la table raw/PREROUTING, AVANT la réécriture NAT de
    # Docker : une règle -I INPUT classique ne voit jamais ce trafic, car
    # Docker a déjà redirigé le paquet vers l'IP du conteneur avant qu'il
    # n'atteigne la chaîne INPUT (il est alors traité en FORWARD).
    # Ceci n'est ni corrigible, ni à contourner : c'est la limite honnête
    # de ce lab avec une seule VM edge.lab disponible (voir la recette). ---
    for p in (port_a, port_b):
        edge.run(f"iptables -t raw -I PREROUTING -p tcp --dport {p} -j DROP")
    try:
        code_a2, _ = _requete(client, "zds.lab.test", adresse, port_a)
        code_b2, _ = _requete(client, "zds.lab.test", adresse, port_b)
        hote_ne_survit_pas = code_a2 != "200" and code_b2 != "200"
    finally:
        for p in (port_a, port_b):
            edge.run(f"iptables -t raw -D PREROUTING -p tcp --dport {p} -j DROP")

    assert hote_ne_survit_pas, message(
        en=f"Blocking both entry point ports must make both unreachable from "
        f"poste.lab (observed entry-a={code_a2!r}, entry-b={code_b2!r}): "
        "they share the same host, this failure is not survivable here.",
        fr=f"Bloquer les deux ports des points d'entrée doit les rendre "
        f"injoignables depuis poste.lab (observé entry-a={code_a2!r}, "
        f"entry-b={code_b2!r}) : ils partagent le même hôte, cette panne "
        "n'est pas survivable ici.",
    )

    assert declare.get("perte_processus") == "survit", message(
        en=f"domaine-de-panne.yaml: 'perte_processus' must be 'survit' "
        f"(measured: process loss survives). Got {declare.get('perte_processus')!r}.",
        fr=f"domaine-de-panne.yaml : « perte_processus » doit valoir "
        f"« survit » (mesuré : la perte d'un processus survit). Reçu "
        f"{declare.get('perte_processus')!r}.",
    )
    assert declare.get("perte_hote") == "ne_survit_pas", message(
        en=f"domaine-de-panne.yaml: 'perte_hote' must be 'ne_survit_pas' "
        f"(measured: host loss does not survive, both entry points share "
        f"edge.lab). Got {declare.get('perte_hote')!r}.",
        fr=f"domaine-de-panne.yaml : « perte_hote » doit valoir "
        f"« ne_survit_pas » (mesuré : la perte de l'hôte ne survit pas, "
        f"les deux points d'entrée partagent edge.lab). Reçu "
        f"{declare.get('perte_hote')!r}.",
    )


def _regenerer_certificat_sain(edge) -> None:
    """Redépose une paire crt/key cohérente, sans passer par l'outil testé.

    Sert de filet de sécurité en fin de test : que la rotation concurrente
    ait laissé une paire saine ou dépareillée, ce test doit rendre la main
    sur un couple qui se parse et se correspond, faute de quoi le reste de
    la suite (et le rejeu de la solution de référence dans un autre module)
    resterait bloqué à jamais sur une sonde TLS qui ne converge jamais : un
    couple dépareillé n'est corrigé par rien d'autre dans ce lab tant que
    personne n'y régénère un certificat.
    """
    edge.run(
        f"openssl req -x509 -newkey rsa:2048 -nodes "
        f"-keyout {TLS}/tls.key -out {TLS}/tls.crt -days 1 "
        f'-subj "/CN=zds.lab.test" -addext "subjectAltName=DNS:zds.lab.test" '
        f"2>/dev/null"
    )


def test_certificat_partage_resiste_a_une_rotation_concurrente(edge, ports) -> None:
    try:
        for _ in range(8):
            # Attend réellement la fin des deux rotations concurrentes (via
            # job control + wait) plutôt qu'un sleep deviné : des processus
            # détachés qui traînent après le sleep continueraient d'écrire
            # tls.crt/tls.key bien après la fin du test et corrompraient
            # l'état des tests suivants (y compris, dans un autre module,
            # le rejeu de la solution de référence).
            edge.run(
                f"timeout 15 bash -c '{OUTIL} & p1=$!; {OUTIL} & p2=$!; wait $p1 $p2'"
            )

            crt_ok = edge.run(f"openssl x509 -in {TLS}/tls.crt -noout 2>/dev/null")
            cle_ok = edge.run(f"openssl pkey -in {TLS}/tls.key -noout 2>/dev/null")
            assert crt_ok.rc == 0 and cle_ok.rc == 0, message(
                en=f"After a concurrent rotation, {TLS}/tls.crt or tls.key does "
                "not parse: the rotation tool is not safe under concurrency. "
                "Write to a temporary path and rename atomically, or serialize "
                "with a lock.",
                fr=f"Après une rotation concurrente, {TLS}/tls.crt ou tls.key ne "
                "se parse plus : l'outil de rotation n'est pas sûr en "
                "concurrence. Écrivez dans un chemin temporaire et renommez de "
                "façon atomique, ou sérialisez avec un verrou.",
            )

            pub_cert = edge.run(f"openssl x509 -in {TLS}/tls.crt -noout -pubkey 2>/dev/null")
            pub_cle = edge.run(f"openssl pkey -in {TLS}/tls.key -pubout 2>/dev/null")
            assert pub_cert.stdout == pub_cle.stdout and pub_cert.stdout, message(
                en=f"After a concurrent rotation, {TLS}/tls.crt and tls.key do "
                "not match: one process's certificate ended up paired with "
                "another's key.",
                fr=f"Après une rotation concurrente, {TLS}/tls.crt et tls.key ne "
                "correspondent plus : le certificat d'une exécution s'est "
                "retrouvé apparié à la clé d'une autre.",
            )
    finally:
        # Quel que soit le verdict ci-dessus (y compris un échec attendu sur
        # un outil encore bogué), on repart sur une paire saine : voir le
        # docstring de _regenerer_certificat_sain.
        _regenerer_certificat_sain(edge)

    for nom, port in (("pub-zds-entry-a", ports["ENTREE_A"]), ("pub-zds-entry-b", ports["ENTREE_B"])):
        edge.run(f"docker restart {nom}")
        code = None
        for _ in range(20):
            code, _ = _requete(edge, "zds.lab.test", "127.0.0.1", port)
            if code == "200":
                break
            time.sleep(1)
        assert code == "200", message(
            en=f"{nom} does not serve a working TLS handshake after the "
            "certificate rotation stress.",
            fr=f"{nom} ne sert plus de poignée de main TLS fonctionnelle "
            "après le test de charge sur la rotation de certificat.",
        )
