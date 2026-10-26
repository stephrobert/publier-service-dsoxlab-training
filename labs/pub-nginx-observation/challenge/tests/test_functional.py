"""Verify the status endpoint, a structured access log, timings that really
measure, and upstream errors recorded as such.

CE QUE CHAQUE TEST DOIT POUVOIR DIRE

« Serait-il vert si l'apprenant ne faisait rien ? » Le setup pose Nginx
publiant l'application avec le journal `combined` par défaut, qui ne porte
ni le temps de réponse ni celui de l'amont, et sans aucun point d'état.

LA PRÉCAUTION QUI TRAVERSE CE FICHIER

Observer, ce n'est pas écrire des champs : c'est écrire des champs qui
DISENT quelque chose. Un journal où `request_time` vaudrait toujours `0.000`
serait structuré, parsable, et parfaitement inutile. Chaque test confronte
donc la valeur journalisée à un fait provoqué : une requête que l'on a
rendue lente, une erreur que l'on a provoquée, un accès que l'on a tenté
depuis une adresse qui doit être refusée.
"""

from __future__ import annotations

import json
import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
URL = "http://app.lab.test"
RESOLUTION = "--resolve app.lab.test:80:127.0.0.1"
JOURNAL = "/opt/pub-nginx-observation/logs/access.log"
# Le backend dort exactement ce temps-là sur /lent. C'est le fait auquel on
# confronte la durée journalisée.
LENTEUR = 2.0


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _lignes_du_journal(edge, depuis: int = 0) -> list[dict]:
    """Les lignes JSON du journal, à partir d'un rang donné.

    Une ligne qui n'est pas du JSON est ignorée ici : c'est le test dédié qui
    le reproche, pour que chaque test échoue sur sa propre raison.
    """
    res = edge.run(f"sudo tail -n +{depuis + 1} {JOURNAL}")
    lignes = []
    for ligne in res.stdout.splitlines():
        brute = ligne.strip()
        if not brute:
            continue
        try:
            lignes.append(json.loads(brute))
        except json.JSONDecodeError:
            continue
    return lignes


def _taille_du_journal(edge) -> int:
    """Le nombre de lignes déjà présentes, pour ne lire ensuite que la suite.

    `sudo wc -l < fichier` serait un piège : le shell ouvre la redirection
    AVANT d'élever les droits, donc la lecture se fait sous le compte
    courant. On passe le chemin en argument.
    """
    res = edge.run(f"sudo wc -l {JOURNAL}")
    premier = res.stdout.strip().split(" ")[0] if res.stdout.strip() else "0"
    return int(premier) if premier.isdigit() else 0


def test_le_point_d_etat_repond_en_local_et_est_refuse_de_l_exterieur(
    edge, ip_edge
) -> None:
    """Les deux moitiés comptent, et la seconde est celle qu'on oublie.

    Un `stub_status` exposé à tous donne à n'importe qui le nombre de
    connexions en cours du service. L'exposer sur la boucle locale seule est
    le geste ; vérifier qu'il répond ne prouve que la moitié de ce geste.
    """
    local = edge.run(
        "curl --max-time 5 --silent --show-error http://127.0.0.1:8081/nginx_status"
    )
    assert local.rc == 0 and "Active connections" in local.stdout, message(
        en=(
            "http://127.0.0.1:8081/nginx_status does not answer with the status "
            "page. Expose `stub_status` on the loopback interface "
            f"(answer: {local.stdout.strip()[:160]!r})."
        ),
        fr=(
            "http://127.0.0.1:8081/nginx_status ne rend pas la page d'état. "
            "Exposez `stub_status` sur l'interface de bouclage "
            f"(réponse : {local.stdout.strip()[:160]!r})."
        ),
    )
    distant = edge.run(
        f"curl --max-time 5 --silent --output /dev/null "
        f"--write-out '%{{http_code}}' http://{ip_edge}:8081/nginx_status"
    )
    code = distant.stdout.strip()
    assert code != "200", message(
        en=(
            f"The status page also answers on {ip_edge}, the lab network address: "
            "anyone can read the service's live connection counts. Bind that "
            "listener to the loopback interface, or deny the other addresses."
        ),
        fr=(
            f"La page d'état répond aussi sur {ip_edge}, l'adresse du réseau du "
            "lab : n'importe qui y lit le nombre de connexions en cours du "
            "service. Liez cette écoute à l'interface de bouclage, ou refusez les "
            "autres adresses."
        ),
    )


def test_le_journal_est_structure_ligne_par_ligne(edge) -> None:
    """Chaque ligne est un objet JSON, et porte les champs qu'on exploitera.

    « Parsable » se vérifie en parsant. Chercher une accolade dans le fichier
    dirait oui sur un journal à moitié converti, qui est précisément l'état
    où un collecteur rejette une ligne sur deux sans que personne le voie.
    """
    avant = _taille_du_journal(edge)
    edge.run(f"curl --max-time 5 --silent --output /dev/null {RESOLUTION} {URL}/sonde")
    time.sleep(1)

    res = edge.run(f"sudo tail -n +{avant + 1} {JOURNAL}")
    brutes = [ligne for ligne in res.stdout.splitlines() if ligne.strip()]
    assert brutes, message(
        en=(
            f"Nothing was written to {JOURNAL} for a request that was served. "
            "The access log must record the application's traffic."
        ),
        fr=(
            f"Rien n'a été écrit dans {JOURNAL} pour une requête pourtant servie. "
            "Le journal d'accès doit enregistrer le trafic de l'application."
        ),
    )
    non_json = []
    for brute in brutes:
        try:
            json.loads(brute)
        except json.JSONDecodeError:
            non_json.append(brute.strip()[:120])
    assert not non_json, message(
        en=(
            "These log lines are not JSON objects, so a collector would drop "
            f"them: {non_json[:3]}. Declare a `log_format` that emits one JSON "
            "object per line, and use it on the application's access_log."
        ),
        fr=(
            "Ces lignes de journal ne sont pas des objets JSON, un collecteur les "
            f"rejetterait donc : {non_json[:3]}. Déclarez un `log_format` qui "
            "émet un objet JSON par ligne, et employez-le sur l'access_log de "
            "l'application."
        ),
    )

    requis = {"status", "request_time", "upstream_response_time"}
    derniere = json.loads(brutes[-1])
    manquants = sorted(requis - set(derniere))
    assert not manquants, message(
        en=(
            f"The log line carries none of these fields: {manquants}. Without "
            "them, a slow page cannot be told apart from a slow application."
        ),
        fr=(
            f"La ligne de journal ne porte pas ces champs : {manquants}. Sans "
            "eux, une page lente ne se distingue pas d'une application lente."
        ),
    )


def test_la_duree_journalisee_mesure_vraiment(edge) -> None:
    """LE test du lab : la durée écrite correspond à une lenteur provoquée.

    Un `request_time` présent mais toujours à `0.000` passerait le test
    précédent sans rien apprendre à personne. On demande donc une page dont
    on SAIT qu'elle met deux secondes, et on exige que le journal le dise.
    """
    avant = _taille_du_journal(edge)
    debut = time.monotonic()
    edge.run(
        f"curl --max-time 15 --silent --output /dev/null {RESOLUTION} {URL}/lent"
    )
    reelle = time.monotonic() - debut
    time.sleep(1)

    lignes = _lignes_du_journal(edge, avant)
    lentes = [
        ligne for ligne in lignes
        if "/lent" in str(ligne.get("request", "")) + str(ligne.get("uri", ""))
    ]
    assert lentes, message(
        en=(
            f"No log line mentions /lent, although the request took {reelle:.1f} s. "
            "The logged line must carry the requested path."
        ),
        fr=(
            f"Aucune ligne de journal ne mentionne /lent, alors que la requête a "
            f"duré {reelle:.1f} s. La ligne journalisée doit porter le chemin "
            "demandé."
        ),
    )
    try:
        duree = float(str(lentes[-1].get("request_time", "")).strip() or 0)
    except ValueError:
        duree = 0.0
    assert duree >= LENTEUR * 0.8, message(
        en=(
            f"The log says request_time={duree}, for a request that really took "
            f"{reelle:.1f} s against a backend that sleeps {LENTEUR} s. The field "
            "is present but does not measure: check it is `$request_time` and not "
            "a constant."
        ),
        fr=(
            f"Le journal indique request_time={duree}, pour une requête qui a "
            f"réellement duré {reelle:.1f} s face à un backend qui dort "
            f"{LENTEUR} s. Le champ est présent mais ne mesure rien : vérifiez "
            "qu'il vaut bien `$request_time` et non une constante."
        ),
    )


def test_l_erreur_de_l_amont_est_enregistree_comme_telle(edge) -> None:
    """Une erreur du backend se retrouve dans le journal, et le normal reste normal.

    Les deux moitiés, encore : un journal qui écrirait 503 partout
    satisferait la première et serait faux.
    """
    avant = _taille_du_journal(edge)
    edge.run(f"curl --max-time 5 --silent --output /dev/null {RESOLUTION} {URL}/casse")
    edge.run(f"curl --max-time 5 --silent --output /dev/null {RESOLUTION} {URL}/health")
    time.sleep(1)

    lignes = _lignes_du_journal(edge, avant)
    statuts = {}
    for ligne in lignes:
        chemin = str(ligne.get("request", "")) + str(ligne.get("uri", ""))
        for marque in ("/casse", "/health"):
            if marque in chemin:
                statuts[marque] = str(ligne.get("status", "")).strip()

    assert statuts.get("/casse") == "503", message(
        en=(
            "The upstream error on /casse is not recorded as a 503 "
            f"(found: {statuts.get('/casse')!r}). An observability setup that "
            "hides failures observes nothing worth having."
        ),
        fr=(
            "L'erreur de l'amont sur /casse n'est pas enregistrée en 503 "
            f"(trouvé : {statuts.get('/casse')!r}). Une observabilité qui cache "
            "les échecs n'observe rien qui vaille."
        ),
    )
    assert statuts.get("/health") == "200", message(
        en=(
            "The healthy request on /health is not recorded as a 200 "
            f"(found: {statuts.get('/health')!r}). A log that reports the same "
            "status for everything distinguishes nothing."
        ),
        fr=(
            "La requête saine sur /health n'est pas enregistrée en 200 "
            f"(trouvé : {statuts.get('/health')!r}). Un journal qui rapporte le "
            "même statut pour tout ne distingue rien."
        ),
    )
