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
FENETRE_DETECTION_S = 5
FENETRE_STABLE_S = 5
ERREURS_ARRET_TOLEREES = 1
DELAI_RETOUR_S = 40


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


def _trace_requetes(
    hote, n: int, pause: str = "0.05", avant: str = "", host: str = HOTE
) -> tuple[float, list[tuple[float, str, str | None]]]:
    """Rend l'heure de départ et (heure, code HTTP, hostname) de chaque requête."""
    script = (
        "printf 'DEBUT=%s\\n' \"$(date +%s.%N)\"\n"
        f"{avant}\n"
        f"for i in $(seq 1 {n}); do "
        "printf '\\nPROBE=%s\\n' \"$(date +%s.%N)\"; "
        f"curl -s -m 3 -H 'Host: {host}' -w '\\nHTTPCODE=%{{http_code}}\\n' "
        "http://127.0.0.1:80/; "
        f"sleep {pause}; done\n"
        "wait"
    )
    sortie = hote.run(script).stdout
    debut = re.search(r"DEBUT=([0-9.]+)", sortie)
    assert debut, "impossible de dater le début de la séquence de requêtes"
    requetes = []
    for horodatage, corps, code in re.findall(
        r"PROBE=([0-9.]+)\n(.*?)\nHTTPCODE=(\d{3})", sortie, re.S
    ):
        hostname = re.search(r"^Hostname: (\S+)", corps, re.M)
        requetes.append(
            (float(horodatage), code, hostname.group(1) if hostname else None)
        )
    return float(debut.group(1)), requetes


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


def test_une_instance_arretee_bascule_sans_erreur_apres_detection(edge) -> None:
    backends = _backends(edge)
    assert len(backends) >= 2, message(
        en="Two instances are needed to test the loss of one.",
        fr="Il faut deux instances pour tester la perte de l'une.",
    )
    (nom, ident), (_, autre) = backends[0], backends[1]
    try:
        debut, rep = _trace_requetes(
            edge,
            200,
            pause="0.05",
            avant=f"docker stop -t 1 {nom} >/dev/null &",
        )
        etat = edge.run(f"docker inspect -f '{{{{.State.Running}}}}' {nom}")
        assert etat.stdout.strip() == "false", message(
            en=f"{nom} was not actually stopped during the request sequence.",
            fr=f"{nom} n'a pas réellement été arrêté pendant la séquence de requêtes.",
        )
        fenetre = [r for r in rep if r[0] - debut <= FENETRE_DETECTION_S]
        stable = [r for r in rep if r[0] - debut > FENETRE_DETECTION_S]
        erreurs_fenetre = [r for r in fenetre if r[1] != "200"]
        erreurs_stables = [r for r in stable if r[1] != "200"]
        dernier_envoi = max(
            (r[0] - debut for r in rep if r[2] == ident),
            default=0.0,
        )
        assert len(rep) == 200, message(
            en=f"Expected 200 timestamped requests, but parsed {len(rep)}.",
            fr=f"Il fallait 200 requêtes horodatées, mais {len(rep)} ont été lues.",
        )
        assert len(erreurs_fenetre) <= ERREURS_ARRET_TOLEREES, message(
            en=f"{nom} caused {len(erreurs_fenetre)} client error(s) in the "
            f"{FENETRE_DETECTION_S}s detection window; at most "
            f"{ERREURS_ARRET_TOLEREES} is tolerated from the measured handover.",
            fr=f"{nom} a causé {len(erreurs_fenetre)} erreur(s) client pendant "
            f"la fenêtre de détection de {FENETRE_DETECTION_S}s ; "
            f"{ERREURS_ARRET_TOLEREES} au maximum est tolérée pendant le basculement mesuré.",
        )
        assert dernier_envoi <= FENETRE_DETECTION_S, message(
            en=f"Traefik sent traffic to stopped instance {nom} for "
            f"{dernier_envoi:.2f}s; the detection limit is {FENETRE_DETECTION_S}s.",
            fr=f"Traefik a envoyé du trafic à l'instance arrêtée {nom} pendant "
            f"{dernier_envoi:.2f}s ; la limite de détection est "
            f"{FENETRE_DETECTION_S}s.",
        )
        assert (
            len(stable) >= 80
            and stable[-1][0] - stable[0][0] >= FENETRE_STABLE_S
            and not erreurs_stables
            and all(r[2] == autre for r in stable)
        ), message(
            en=f"After the {FENETRE_DETECTION_S}s detection window, expected "
            f"{FENETRE_STABLE_S}s of error-free traffic only to {autre}; got "
            f"{len(stable)} requests, errors={len(erreurs_stables)}, "
            f"backends={sorted({r[2] for r in stable})}.",
            fr=f"Après la fenêtre de détection de {FENETRE_DETECTION_S}s, il "
            f"fallait {FENETRE_STABLE_S}s de trafic sans erreur vers {autre} "
            f"uniquement ; reçu {len(stable)} requêtes, "
            f"erreurs={len(erreurs_stables)}, "
            f"backends={sorted({r[2] for r in stable})}.",
        )
    finally:
        edge.run(f"docker start {nom}")
    vus: set = set()
    limite = time.time() + DELAI_RETOUR_S
    while time.time() < limite and ident not in vus:
        vus |= {h for c, h in _requetes(edge, 10, pause="0.1") if c == "200"}
    assert ident in vus, message(
        en=f"{nom} was started again but never took traffic back within "
        f"{DELAI_RETOUR_S}s.",
        fr=f"{nom} a ete redemarre mais n'a pas repris de trafic en "
        f"{DELAI_RETOUR_S}s.",
    )


def test_une_instance_malade_ne_recoit_plus_de_trafic(edge) -> None:
    backends = _backends(edge)
    assert len(backends) >= 2, message(
        en="Two instances are needed to test the sickness of one.",
        fr="Il faut deux instances pour tester la maladie de l'une.",
    )
    (nom, ident), (_, autre) = backends[0], backends[1]
    ip = _ip(edge, nom)
    try:
        res = edge.run(
            f"printf 'MALADIE=%s\\n' \"$(date +%s.%N)\"; "
            f"curl -s -m 3 -o /dev/null -w '%{{http_code}}' "
            f"-X POST -d 500 http://{ip}/health"
        )
        assert res.stdout.rstrip().endswith("200"), (
            f"impossible de rendre {nom} malade : {res.stdout!r}"
        )
        maladie = re.search(r"MALADIE=([0-9.]+)", res.stdout)
        assert maladie, "impossible de dater l'injection de la panne"
        instant_maladie = float(maladie.group(1))
        _, rep = _trace_requetes(edge, 200, pause="0.05")
        assert len(rep) == 200, message(
            en=f"Expected 200 timestamped requests, but parsed {len(rep)}.",
            fr=f"Il fallait 200 requêtes horodatées, mais {len(rep)} ont été lues.",
        )
        stable = [
            r for r in rep if r[0] - instant_maladie > FENETRE_DETECTION_S
        ]
        dernier_envoi = max(
            (r[0] - instant_maladie for r in rep if r[2] == ident),
            default=0.0,
        )
        assert dernier_envoi <= FENETRE_DETECTION_S, message(
            en=f"{nom} remained in rotation for {dernier_envoi:.2f}s after its "
            f"/health check failed; the detection limit is {FENETRE_DETECTION_S}s.",
            fr=f"{nom} est resté dans la rotation pendant {dernier_envoi:.2f}s "
            f"après l'échec de /health ; la limite de détection est "
            f"{FENETRE_DETECTION_S}s.",
        )
        assert (
            len(stable) >= 80
            and stable[-1][0] - stable[0][0] >= FENETRE_STABLE_S
            and all(r[1] == "200" and r[2] == autre for r in stable)
            and all(r[1] == "200" for r in rep)
        ), message(
            en=f"Expected {FENETRE_STABLE_S}s of error-free traffic only to "
            f"{autre} after detection; observed {len(stable)} requests and "
            f"backends={sorted({r[2] for r in stable})}.",
            fr=f"Il fallait {FENETRE_STABLE_S}s de trafic sans erreur vers "
            f"{autre} uniquement après détection ; reçu {len(stable)} requêtes "
            f"et backends={sorted({r[2] for r in stable})}.",
        )
    finally:
        edge.run(f"curl -s -m 3 -o /dev/null -X POST -d 200 http://{ip}/health")
    vus: set = set()
    limite = time.time() + DELAI_RETOUR_S
    while time.time() < limite and ident not in vus:
        vus |= {h for c, h in _requetes(edge, 10, pause="0.1") if c == "200"}
    assert ident in vus, message(
        en=f"{nom} became healthy again but did not take traffic back within "
        f"{DELAI_RETOUR_S}s.",
        fr=f"{nom} est redevenu sain mais n'a pas repris de trafic en "
        f"{DELAI_RETOUR_S}s.",
    )
