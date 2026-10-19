"""Ce qu'un client voit de Traefik, et ce que la machine publie vraiment.

Aucun test ne lit le Compose de l'apprenant. Ils envoient des requetes comme
un client le ferait (`Host: whoami.lab.test` sur le port 80), lisent ce que
Docker publie, puis provoquent eux-memes deux pannes sur une instance :

- un `docker stop` : Traefik garde l'instance dans sa liste un court instant
  (le fournisseur Docker temporise ses mises a jour), et les requetes de ce
  laps de temps partent vers un serveur mort si rien ne les rejoue ;
- un `POST /health` qui rend l'instance malade alors qu'elle tourne : seule une
  sonde active la retire du tour, parce que Docker, lui, la voit vivante.

Chaque panne est reparee par le test, meme quand il echoue.
"""

from __future__ import annotations

import re
import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")

HOTE = "whoami.lab.test"
TEMOIN = "pub-interne"
DIGEST_TRAEFIK = "sha256:0f6150202bc1fed72a7bd2107460eaa510e5b8a905f3fdb5b84f2c8619c33368"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _backends(hote) -> list[tuple[str, str]]:
    """(nom, id court) des instances whoami en cours, le temoin exclu."""
    # Pas de `--filter ancestor` : il ne retrouve pas une image tiree par digest.
    res = hote.run("docker ps --format '{{.Names}} {{.ID}} {{.Image}}'")
    out = []
    for ligne in res.stdout.splitlines():
        nom, ident, image = ligne.split()
        if image.startswith("traefik/whoami") and nom != TEMOIN:
            out.append((nom, ident))
    return out


def _requetes(hote, n: int, pause: str = "0.05", avant: str = "", host: str = HOTE):
    """n requetes en boucle ; rend [(code, hostname_ou_None)]. `avant` est lance d'abord."""
    script = (
        f"{avant}\n"
        f"for i in $(seq 1 {n}); do "
        f"curl -s -m 3 -H 'Host: {host}' -w '\\nHTTPCODE=%{{http_code}}\\n' "
        "http://127.0.0.1:80/; "
        f"sleep {pause}; done\n"
        "wait"
    )
    res = hote.run(script)
    blocs = res.stdout.split("HTTPCODE=")
    rep = []
    for i in range(len(blocs) - 1):
        corps = blocs[i]
        code = blocs[i + 1].split("\n", 1)[0].strip()
        m = re.search(r"^Hostname: (\S+)", corps, re.M)
        rep.append((code, m.group(1) if m else None))
    return rep


def _ip(hote, nom: str) -> str:
    res = hote.run(
        "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' " + nom
    )
    return res.stdout.split()[0]


def test_traefik_repartit_la_charge_sur_deux_instances(edge) -> None:
    backends = _backends(edge)
    assert len(backends) >= 2, message(
        en=f"Found {len(backends)} traefik/whoami instance(s) besides {TEMOIN}; two are expected.",
        fr=f"{len(backends)} instance(s) traefik/whoami hors {TEMOIN} ; il en faut deux.",
    )
    rep = _requetes(edge, 30)
    codes = {c for c, _ in rep}
    assert codes == {"200"} and len(rep) == 30, message(
        en=f"{HOTE} on port 80 did not answer 200 every time (got {sorted(codes)}). Is "
        "Traefik up, publishing 80, with a router for that host on the backends?",
        fr=f"{HOTE} sur le port 80 n'a pas toujours repondu 200 (recu {sorted(codes)}). "
        "Traefik tourne-t-il, publie-t-il 80, avec une route pour ce nom sur les backends ?",
    )
    vus = {h for _, h in rep}
    ids = {i for _, i in backends}
    assert len(vus & ids) >= 2, message(
        en=f"Only {sorted(vus)} answered: the load is not shared between two instances.",
        fr=f"Seuls {sorted(vus)} ont repondu : la charge n'est pas partagee entre deux instances.",
    )


def test_rien_n_est_expose_par_defaut(edge) -> None:
    rep = _requetes(edge, 3, host=TEMOIN)
    codes = {c for c, _ in rep}
    assert codes == {"404"}, message(
        en=f"{TEMOIN} carries no Traefik label yet answered {sorted(codes)} through it. "
        "Discovery must be opt-in (exposedbydefault=false).",
        fr=f"{TEMOIN} ne porte aucune etiquette Traefik mais repond {sorted(codes)} a "
        "travers lui. La decouverte doit etre sur adhesion (exposedbydefault=false).",
    )


def test_aucun_port_de_backend_publie(edge) -> None:
    backends = _backends(edge)
    assert backends, message(en="No backend is running.", fr="Aucun backend ne tourne.")
    for nom, _ in backends:
        res = edge.run(f"docker port {nom}")
        assert res.stdout.strip() == "", message(
            en=f"{nom} publishes a port on the host ({res.stdout.strip()!r}): clients would "
            "bypass the proxy. Backends must stay reachable only through Traefik.",
            fr=f"{nom} publie un port sur l'hote ({res.stdout.strip()!r}) : un client "
            "contournerait le proxy. Les backends ne doivent etre joignables que par Traefik.",
        )


def test_traefik_est_epingle_par_digest(edge) -> None:
    res = edge.run(
        "docker ps --format '{{.ID}} {{.Image}}' | grep -E ' traefik[:@]' | cut -d' ' -f1 | "
        "while read c; do "
        "docker image inspect -f '{{json .RepoDigests}}' $(docker inspect -f '{{.Image}}' $c); done"
    )
    assert DIGEST_TRAEFIK in res.stdout, message(
        en="No running Traefik container uses the pinned image traefik:v3.7.15@sha256:0f61... "
        "(see LISEZ-MOI.txt).",
        fr="Aucun conteneur Traefik n'utilise l'image epinglee traefik:v3.7.15@sha256:0f61... "
        "(voir LISEZ-MOI.txt).",
    )


def test_une_instance_arretee_ne_cause_aucune_erreur(edge) -> None:
    backends = _backends(edge)
    assert len(backends) >= 2, message(
        en="Two instances are needed to test the loss of one.",
        fr="Il faut deux instances pour tester la perte de l'une.",
    )
    nom, ident = backends[0]
    try:
        rep = _requetes(edge, 100, avant=f"docker stop -t 1 {nom} >/dev/null &")
        erreurs = [c for c, _ in rep if c != "200"]
        assert not erreurs and len(rep) == 100, message(
            en=f"While {nom} was stopped, the client received {len(erreurs)} error(s) "
            f"({sorted(set(erreurs))}). Traefik keeps a stopped container in its list for a "
            "moment: replay failed requests on the other instance (retry middleware).",
            fr=f"Pendant l'arret de {nom}, le client a recu {len(erreurs)} erreur(s) "
            f"({sorted(set(erreurs))}). Traefik garde un conteneur arrete dans sa liste un "
            "instant : rejouez les requetes echouees sur l'autre instance (middleware retry).",
        )
    finally:
        edge.run(f"docker start {nom}")
    vus: set = set()
    limite = time.time() + 40
    while time.time() < limite and ident not in vus:
        vus |= {h for _, h in _requetes(edge, 10, pause="0.1")}
    assert ident in vus, message(
        en=f"{nom} was started again but never took traffic back within 40 s.",
        fr=f"{nom} a ete redemarre mais n'a pas repris de trafic en 40 s.",
    )


def test_une_instance_malade_ne_recoit_plus_de_trafic(edge) -> None:
    backends = _backends(edge)
    assert len(backends) >= 2, message(
        en="Two instances are needed to test the sickness of one.",
        fr="Il faut deux instances pour tester la maladie de l'une.",
    )
    (nom, _), (_, autre) = backends[0], backends[1]
    ip = _ip(edge, nom)
    try:
        res = edge.run(f"curl -s -m 3 -o /dev/null -w '%{{http_code}}' -X POST -d 500 http://{ip}/health")
        assert res.stdout.strip() == "200", f"impossible de rendre {nom} malade : {res.stdout!r}"
        limite = time.time() + 40
        propre = False
        while time.time() < limite and not propre:
            rep = _requetes(edge, 15, pause="0.1")
            propre = len(rep) == 15 and all(c == "200" and h == autre for c, h in rep)
        assert propre, message(
            en=f"{nom} reports 500 on /health but still takes traffic after 40 s. A container "
            "that runs is not a container that works: add an active health check "
            "(loadbalancer.healthcheck.path).",
            fr=f"{nom} repond 500 sur /health mais recoit encore du trafic apres 40 s. Un "
            "conteneur qui tourne n'est pas un conteneur qui fonctionne : ajoutez une sonde "
            "active (loadbalancer.healthcheck.path).",
        )
    finally:
        edge.run(f"curl -s -m 3 -o /dev/null -X POST -d 200 http://{ip}/health")
