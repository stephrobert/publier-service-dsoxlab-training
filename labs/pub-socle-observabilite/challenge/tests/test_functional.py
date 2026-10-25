"""Vérifie le SLI, l'alerte, la corrélation et la distinction des causes
d'un diagnostic silencieux, pour le lab pub-socle-observabilite.

Chaque test restaure l'état qu'il a changé (drapeau de panne retiré,
générateur relancé, exportateur dégelé), pour que la suite reste rejouable
dans les deux sens par le validateur.
"""

from __future__ import annotations

import json
import time

import pytest
import yaml

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
ETAT = "/var/lib/pub-obs/etat.json"
ACCES_LOG = "/var/log/pub-obs/acces.log"
PANNE_FLAG = "/var/lib/pub-obs/panne"
SLI_FICHIER = "/home/student/sli.yaml"
CORRELATION_FICHIER = "/home/student/correlation.yaml"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


def _lire_journal(edge) -> list[dict]:
    brut = edge.run(f"sudo cat {ACCES_LOG}").stdout
    evts = []
    for ligne in brut.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            evts.append(json.loads(ligne))
        except json.JSONDecodeError:
            continue
    return evts


def _appliquer_sli(evts: list[dict], sli: dict, lot: str) -> tuple[int, int]:
    route = sli.get("route")
    exclut = set(sli.get("exclut") or [])
    cmin = sli.get("code_min_succes")
    cmax = sli.get("code_max_succes")
    total = succes = 0
    for e in evts:
        if e.get("lot") != lot:
            continue
        if e.get("route") in exclut:
            continue
        if e.get("route") != route:
            continue
        total += 1
        if cmin is not None and cmax is not None and cmin <= e.get("code", 0) <= cmax:
            succes += 1
    return total, succes


def _diagnostic(edge, port: int) -> dict:
    res = edge.run(f"curl -s --max-time 3 http://127.0.0.1:{port}/diagnostic")
    return json.loads(res.stdout)


def _attendre(edge, port: int, predicat, limite_s: float) -> dict:
    limite = time.monotonic() + limite_s
    dernier: dict = {}
    while time.monotonic() < limite:
        dernier = _diagnostic(edge, port)
        if predicat(dernier):
            return dernier
        time.sleep(1)
    return dernier


@pytest.fixture
def sli(edge):
    fichier = edge.file(SLI_FICHIER)
    assert fichier.exists, message(
        en=f"{SLI_FICHIER} does not exist.", fr=f"{SLI_FICHIER} n'existe pas."
    )
    try:
        return yaml.safe_load(fichier.content_string) or {}
    except yaml.YAMLError as erreur:
        pytest.fail(message(
            en=f"{SLI_FICHIER} is not valid YAML: {erreur}",
            fr=f"{SLI_FICHIER} n'est pas un YAML valide : {erreur}",
        ))


def test_sli_sur_le_lot_historique(edge, sli) -> None:
    evts = _lire_journal(edge)
    total, succes = _appliquer_sli(evts, sli, "historique")
    assert (total, succes) == (10, 5), message(
        en=f"Applying your sli.yaml to the historical batch gives total={total}, "
        f"success={succes}; it must give total=10, success=5. '/sante' is noise, "
        f"not a business route, and must not be counted.",
        fr=f"Appliquer votre sli.yaml au lot historique donne total={total}, "
        f"succes={succes} ; il faut total=10, succes=5. '/sante' est du bruit, "
        f"pas une route d'affaires, et ne doit pas être compté.",
    )


def test_sli_sur_du_trafic_vivant(edge, etat, sli) -> None:
    port = etat["port_metier"]
    lot = "vivant-" + str(int(time.time()))
    try:
        for i in range(6):
            edge.run(
                f"curl -s -o /dev/null -H 'X-Request-Id: {lot}-ok-{i}' "
                f"-H 'X-Batch-Id: {lot}' http://127.0.0.1:{port}/commande"
            )
        edge.run(f"sudo touch {PANNE_FLAG}")
        for i in range(4):
            edge.run(
                f"curl -s -o /dev/null -H 'X-Request-Id: {lot}-ko-{i}' "
                f"-H 'X-Batch-Id: {lot}' http://127.0.0.1:{port}/commande"
            )
    finally:
        edge.run(f"sudo rm -f {PANNE_FLAG}")
    for i in range(3):
        edge.run(
            f"curl -s -o /dev/null -H 'X-Request-Id: {lot}-sante-{i}' "
            f"-H 'X-Batch-Id: {lot}' http://127.0.0.1:{port}/sante"
        )

    evts = _lire_journal(edge)
    total, succes = _appliquer_sli(evts, sli, lot)
    assert (total, succes) == (10, 6), message(
        en=f"Applying your sli.yaml to this fresh, known batch (6 successes and "
        f"4 failures on /commande, plus 3 noise requests on /sante) gives "
        f"total={total}, success={succes}; it must give total=10, success=6.",
        fr=f"Appliquer votre sli.yaml à ce lot frais et connu (6 succès et 4 "
        f"échecs sur /commande, plus 3 requêtes de bruit sur /sante) donne "
        f"total={total}, succes={succes} ; il faut total=10, succes=6.",
    )


def test_correlation_de_l_incident(edge, etat) -> None:
    incident_id = etat["incident_id"]
    evts = _lire_journal(edge)
    lignes = [e for e in evts if e.get("id") == incident_id]
    assert lignes, message(
        en=f"No log line found for incident id {incident_id}.",
        fr=f"Aucune ligne de journal trouvée pour l'identifiant d'incident {incident_id}.",
    )
    reel = lignes[0]

    fichier = edge.file(CORRELATION_FICHIER)
    assert fichier.exists, message(
        en=f"{CORRELATION_FICHIER} does not exist.",
        fr=f"{CORRELATION_FICHIER} n'existe pas.",
    )
    try:
        rapporte = yaml.safe_load(fichier.content_string) or {}
    except yaml.YAMLError as erreur:
        pytest.fail(message(
            en=f"{CORRELATION_FICHIER} is not valid YAML: {erreur}",
            fr=f"{CORRELATION_FICHIER} n'est pas un YAML valide : {erreur}",
        ))

    assert rapporte.get("requete_id") == incident_id, message(
        en="'requete_id' does not match the incident named in the README.",
        fr="'requete_id' ne correspond pas à l'incident nommé dans le README.",
    )
    assert rapporte.get("backend") == "pub-obs-metier", message(
        en="'backend' must be 'pub-obs-metier': this lab has a single backend.",
        fr="'backend' doit valoir 'pub-obs-metier' : ce lab n'a qu'un seul backend.",
    )
    assert rapporte.get("code") == reel.get("code"), message(
        en=f"'code' is wrong: the log line really shows {reel.get('code')}.",
        fr=f"'code' est faux : la ligne de journal montre réellement {reel.get('code')}.",
    )
    assert rapporte.get("duree_ms") == reel.get("latence_ms"), message(
        en=f"'duree_ms' is wrong: the log line really shows {reel.get('latence_ms')} ms.",
        fr=f"'duree_ms' est faux : la ligne de journal montre réellement {reel.get('latence_ms')} ms.",
    )


def test_alerte_se_declenche_sur_la_panne_et_se_resout(edge, etat) -> None:
    port = etat["port_evaluateur"]
    try:
        edge.run(f"sudo touch {PANNE_FLAG}")
        diag = _attendre(edge, port, lambda d: d.get("classification") == "panne_reelle", 25)
        assert diag.get("classification") == "panne_reelle" and diag.get("firing") is True, message(
            en=f"The evaluator never classified the injected outage as 'panne_reelle' "
            f"with firing=true within 25s: {diag}. 'alerte.seuil_taux_erreur' is "
            f"probably still unreachable.",
            fr=f"L'évaluateur n'a jamais classé la panne injectée en 'panne_reelle' "
            f"avec firing=true en 25 s : {diag}. 'alerte.seuil_taux_erreur' est "
            f"probablement encore hors d'atteinte.",
        )
    finally:
        edge.run(f"sudo rm -f {PANNE_FLAG}")

    diag = _attendre(edge, port, lambda d: d.get("firing") is False, 25)
    assert diag.get("firing") is False, message(
        en=f"The alert never cleared within 25s after the outage was fixed: {diag}.",
        fr=f"L'alerte ne s'est jamais résolue en 25 s après la réparation de la panne : {diag}.",
    )


def test_absence_de_trafic_distincte_d_une_panne(edge, etat) -> None:
    port = etat["port_evaluateur"]
    avant = _attendre(edge, port, lambda d: d.get("classification") == "nominal", 20)
    assert avant.get("classification") == "nominal", message(
        en=f"With the traffic generator running normally and no injected failure, "
        f"the evaluator must classify 'nominal': got {avant}. 'trafic.seuil_minimum' "
        f"is probably still set far too high, hiding real traffic behind a false "
        f"'absence_trafic'.",
        fr=f"Avec le générateur de trafic qui tourne normalement et aucune panne "
        f"injectée, l'évaluateur doit classer 'nominal' : obtenu {avant}. "
        f"'trafic.seuil_minimum' est probablement encore réglé bien trop haut, "
        f"ce qui cache du trafic réel derrière une fausse 'absence_trafic'.",
    )
    try:
        edge.run("sudo systemctl stop pub-obs-generateur.service")
        diag = _attendre(
            edge, port, lambda d: d.get("classification") in ("absence_trafic", "panne_reelle"), 20
        )
        assert diag.get("classification") == "absence_trafic", message(
            en=f"Stopping the traffic generator must be classified 'absence_trafic', "
            f"never 'panne_reelle': got {diag}. 'trafic.seuil_minimum' is probably "
            f"still set far too high.",
            fr=f"Arrêter le générateur de trafic doit être classé 'absence_trafic', "
            f"jamais 'panne_reelle' : obtenu {diag}. 'trafic.seuil_minimum' est "
            f"probablement encore réglé bien trop haut.",
        )
    finally:
        edge.run("sudo systemctl start pub-obs-generateur.service")


def test_collecte_perdue_distincte_d_une_panne(edge, etat) -> None:
    port = etat["port_evaluateur"]
    pid = edge.run("sudo systemctl show -p MainPID --value pub-obs-exportateur.service").stdout.strip()
    assert pid and pid != "0", message(
        en="The exporter service has no MainPID: it is probably not running.",
        fr="Le service exportateur n'a pas de MainPID : il ne tourne probablement pas.",
    )
    try:
        edge.run(f"sudo kill -STOP {pid}")
        time.sleep(14)
        diag = _attendre(
            edge, port,
            lambda d: d.get("classification") in ("collecte_perdue", "panne_reelle", "absence_trafic"),
            20,
        )
        assert diag.get("classification") == "collecte_perdue", message(
            en=f"Freezing the metrics exporter for 14s+ must eventually be classified "
            f"'collecte_perdue': got {diag}. 'collecte.staleness_max_s' is probably "
            f"still far too tolerant.",
            fr=f"Geler l'exportateur de métriques pendant 14 s ou plus doit finir par "
            f"être classé 'collecte_perdue' : obtenu {diag}. 'collecte.staleness_max_s' "
            f"est probablement encore bien trop tolérant.",
        )
    finally:
        edge.run(f"sudo kill -CONT {pid}")
