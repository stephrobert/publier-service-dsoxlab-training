"""Épreuve HAProxy : livrer deux services, les exploiter, puis diagnostiquer une
panne non annoncée.

VINGT TESTS, CINQ DOMAINES, CINQ POINTS CHACUN

dsoxlab note la proportion de tests réussis : le poids d'un domaine est donc
son nombre de tests. Le barème du contrat (publication 20, sécurité 25,
observabilité 20, diagnostic 20, reprise 15) se lit directement :

    01-04  publication et protocoles        4 tests  = 20 points
    05-09  sécurité et confiance            5 tests  = 25 points
    10-13  observabilité et flux            4 tests  = 20 points
    14-17  diagnostic de la panne           4 tests  = 20 points
    18-20  reprise et retour arrière        3 tests  = 15 points

CE QUE LA VALIDATION MESURE, ET CE QU'ELLE NE MESURE PAS

Chaque test lit un COMPORTEMENT : une réponse HTTPS obtenue depuis `poste.lab`
sous vérification TLS stricte, un port fermé, un compteur qui bouge, un
fichier restauré. Aucun test ne lit une directive de HAProxy. Ce qu'une machine
ne sait pas juger (la qualité de l'`explication` du diagnostic, la pertinence
du raisonnement) est lu par un relecteur humain et déclaré tel.

TROIS DISPOSITIONS QUI REVIENNENT

  - Aucun test n'est vert avant le travail. Quand une vérification est vraie
    dès le départ (la panne laisse intacts le canari de confiance, le canari
    de sonde, la limite de débit), elle est FONDUE dans un test qui exige
    d'abord le service réparé : un garde-fou seul donnerait des points à
    l'apprenant qui n'a rien fait.
  - Les certificats de l'autorité de test valent CINQ minutes. Avant chaque
    test qui valide du TLS, la validation exécute le script `renouveler` de
    l'apprenant si un certificat expire dans moins de `marge` secondes. Le
    script est donc exercé tout au long de l'épreuve, pas seulement dans
    le test qui le mesure.
  - L'autorité de test tire une nouvelle racine et oublie ses comptes à chaque
    démarrage. Une vraie autorité ne le fait pas : la validation relit la
    racine avant chaque vérification, et efface le compte local du client
    ACME après le redémarrage de la machine, avant de rejouer le cycle.
"""

from __future__ import annotations

import itertools
import json
import re
import secrets
import shlex
import threading
import time
import unicodedata

import pytest
import yaml

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")

WORK = "/opt/pub-epreuve-haproxy"
RENOUVELER = f"{WORK}/renouveler"
RESTAURER = f"{WORK}/restaurer"
SOCKET = "/run/haproxy/admin.sock"
SAUVEGARDE = "/var/backups/pub-epreuve-haproxy"
SAUVEGARDE_CFG = f"{SAUVEGARDE}/haproxy.cfg.bak"
SAUVEGARDE_DONNEES = f"{SAUVEGARDE}/catalogue.json.bak"
DONNEES = "/var/lib/pub-epreuve-haproxy/catalogue.json"
CHEMIN_TIRAGE = "/root/.pub-epreuve-haproxy-secret.yaml"
INCIDENT_YAML = "/home/student/incident.yaml"
RACINE_POSTE = "/tmp/racine-acme-epreuve.pem"
RAFALE = "/usr/local/bin/rafale"

CATALOGUE = "catalogue.epreuve.test"
NOTIFICATIONS = "notifications.epreuve.test"
NOMS = (CATALOGUE, NOTIFICATIONS)
ADMIN = "ops:Epreuve-Admin-Only"
PORT_METRIQUES = 9101
PORT_ARCHIVES = 8088
PORTS_BACKENDS = (18301, 18302)
# Les seuls ports qui peuvent écouter ailleurs que sur la boucle locale :
# ssh, le point d'entrée (80 et 443) et l'instance « archives » de la panne.
PORTS_AUTORISES = {22, 80, 443, PORT_ARCHIVES}
ADRESSE_FORGEE = "203.0.113.9"

# Un compteur de débit sur 10 s pèse encore sur la période suivante : il se
# vide complètement après DEUX périodes. Attendre moins qu'une fenêtre et demie
# fait lire le reste de la rafale précédente, y compris les requêtes refusées,
# que le compteur compte aussi.
FENETRE_COMPLETE = 22

FAMILLES = ("routage", "sonde", "confiance", "limite", "delai")
# Les signaux qu'un composant bien nommé porte, par famille. Ils sont cherchés
# dans le texte NORMALISÉ (minuscules, sans accent) : jamais une chaîne exacte.
SIGNAUX = {
    "routage": ["route", "routage", "use_backend", "acl", "path", "chemin", "aiguillage"],
    "sonde": ["sonde", "check", "httpchk", "sante", "health", "readiness", "ready"],
    "confiance": [
        "verifyhost",
        "verify",
        "tls",
        "ssl",
        "certificat",
        "confiance",
        "ca-file",
    ],
    "limite": ["limit", "stick", "429", "debit", "http_req_rate", "seuil", "table"],
    "delai": ["timeout", "delai", "borne", "504", "attente", "lent"],
}
# Au-delà d'une famille étrangère citée en plus de la bonne, le composant ne
# nomme plus une cause : il énumère. Une famille de plus reste tolérée, parce
# qu'une cause se décrit souvent par son effet (« la route lente coupée »).
AUTRES_FAMILLES_TOLEREES = 1

MATRICE_ARCHIVES = (
    ("/", "archives-web"),
    ("/archives/liste", "archives-web"),
    ("/v2/produits", "archives-api"),
    ("/v2/lent", "archives-api"),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def ip_edge() -> str:
    return lab_host_ip(CIBLE)


@pytest.fixture(scope="module")
def ip_poste() -> str:
    return lab_host_ip("poste.lab")


@pytest.fixture(scope="module")
def secret(edge) -> dict:
    return yaml.safe_load(edge.run(f"sudo cat {CHEMIN_TIRAGE}").stdout) or {}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def _attendre_retour(machine, limite_s: float = 240.0) -> bool:
    """Attend qu'une machine redémarrée réponde de nouveau.

    `testinfra` LÈVE quand la connexion SSH échoue, au lieu de rendre un
    résultat en échec. Une machine absente pendant son redémarrage n'est pas
    une erreur de test : c'est l'état qu'on attend.
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


def _normaliser(texte: object) -> str:
    brut = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9_.-]+", " ", brut.lower())


def _json(corps: str) -> dict:
    try:
        valeur = json.loads(corps.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {}
    return valeur if isinstance(valeur, dict) else {}


def _port_ouvert(poste, ip: str, port: int) -> bool:
    """Vrai si une connexion TCP depuis le client aboutit."""
    return poste.run(f"timeout 4 bash -c 'exec 3<>/dev/tcp/{ip}/{port}'").rc == 0


def _presente(edge, nom: str) -> dict[str, str]:
    """Le certificat RÉELLEMENT servi pour ce nom, lu par une poignée de main.

    On ne lit pas le fichier du disque : ce qui compte est ce que le service
    présente, et les deux diffèrent d'un seul rechargement oublié.
    """
    sortie = edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
        f"2>/dev/null | openssl x509 -noout -serial -enddate"
    ).stdout
    champs: dict[str, str] = {}
    for ligne in sortie.splitlines():
        if "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            champs[cle.strip()] = valeur.strip()
    assert champs.get("serial"), message(
        en=f"No certificate is served for {nom} on port 443 "
        f"(answer: {sortie.strip()[:160]!r}).",
        fr=f"Aucun certificat n'est servi pour {nom} sur le port 443 "
        f"(réponse : {sortie.strip()[:160]!r}).",
    )
    return champs


def _assurer_certificats(edge, marge: int) -> None:
    """Exécute `renouveler` si un certificat expire dans moins de `marge` s.

    Les certificats de l'autorité de test valent cinq minutes. Sans cette
    étape, un test qui valide du TLS échouerait sur un certificat périmé que
    personne n'a eu le temps de renouveler, et accuserait le service à tort.
    Le script exécuté est CELUI DE L'APPRENANT. Son échec n'est pas jugé ici :
    le test qui suit échoue de lui-même, avec son propre message.
    """
    valides = all(
        edge.run(
            f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
            f"2>/dev/null | openssl x509 -noout -checkend {marge}"
        ).rc
        == 0
        for nom in NOMS
    )
    if not valides and edge.run(f"test -x {RENOUVELER}").rc == 0:
        edge.run(f"sudo {RENOUVELER} 2>&1")


def _racine_courante(edge, poste) -> str:
    """Dépose sur le client la racine que l'autorité de test émet MAINTENANT."""
    res = edge.run("curl -sk --max-time 8 https://localhost:15000/roots/0")
    assert "BEGIN CERTIFICATE" in res.stdout, message(
        en="The test authority does not answer on localhost:15000: the platform "
        "is down, not your service.",
        fr="L'autorité de test ne répond pas sur localhost:15000 : c'est la "
        "plateforme qui est à terre, pas votre service.",
    )
    poste.run(f"printf '%s\\n' {shlex.quote(res.stdout.strip())} > {RACINE_POSTE}")
    return RACINE_POSTE


def _preparer(edge, poste, marge: int = 170) -> str:
    _assurer_certificats(edge, marge)
    return _racine_courante(edge, poste)


def _https(
    poste,
    ip_edge: str,
    nom: str,
    chemin: str,
    *,
    entetes: tuple[str, ...] = (),
    auth: str | None = None,
    avec_racine: bool = True,
    delai: int = 10,
) -> tuple[int, str]:
    """Une requête HTTPS depuis le client indépendant, vérification stricte."""
    commande = [
        "curl",
        "-s",
        "-o",
        "/dev/stdout",
        "-w",
        "\n%{http_code}",
        "--max-time",
        str(delai),
    ]
    if avec_racine:
        commande += ["--cacert", RACINE_POSTE]
    commande += ["--resolve", f"{nom}:443:{ip_edge}"]
    for entete in entetes:
        commande += ["-H", entete]
    if auth:
        commande += ["-u", auth]
    commande.append(f"https://{nom}{chemin}")
    res = poste.run(shlex.join(commande))
    sortie = res.stdout.rsplit("\n", 1)
    corps = sortie[0] if len(sortie) == 2 else ""
    code = int(sortie[-1]) if sortie[-1].strip().isdigit() else 0
    return code, corps


def _rafale(
    poste, ip: str, port: int, hote: str, chemin: str, nombre: int,
    racine: str = "-", pause: float = 0.0,
) -> list[str]:
    res = poste.run(
        shlex.join(
            [RAFALE, ip, str(port), hote, chemin, str(nombre), racine, str(pause)]
        )
    )
    return res.stdout.split()


def _somme(texte: str, metrique: str, filtre: str | None = None) -> float:
    """Somme les échantillons d'une métrique Prometheus, étiquettes confondues."""
    total = 0.0
    for ligne in texte.splitlines():
        if not (ligne.startswith(metrique + "{") or ligne.startswith(metrique + " ")):
            continue
        if filtre and filtre not in ligne:
            continue
        try:
            total += float(ligne.rsplit(" ", 1)[1])
        except ValueError:
            continue
    return total


def _serveurs_down(texte: str) -> int:
    """Nombre de serveurs DOWN d'après `haproxy_server_status`.

    L'exporteur a eu deux formes : une valeur par serveur (0 = DOWN), ou une
    ligne par état avec une étiquette `state` (la ligne `DOWN` vaut 1 quand le
    serveur est tombé). Les deux sont lues, pour ne pas dépendre de la version.
    """
    etats: dict[tuple, dict] = {}
    for ligne in texte.splitlines():
        if not ligne.startswith("haproxy_server_status"):
            continue
        trouve = re.match(r"haproxy_server_status\{([^}]*)\}\s+(\S+)", ligne)
        if not trouve:
            continue
        etiquettes = dict(re.findall(r'(\w+)="([^"]*)"', trouve.group(1)))
        cle = (etiquettes.get("proxy"), etiquettes.get("server"))
        etats.setdefault(cle, {})[etiquettes.get("state")] = float(trouve.group(2))
    tombes = 0
    for valeurs in etats.values():
        if None in valeurs:
            tombes += 1 if valeurs[None] == 0 else 0
        elif valeurs.get("DOWN") == 1.0:
            tombes += 1
    return tombes


def _metriques(edge) -> str:
    res = edge.run(f"curl -s --max-time 5 http://127.0.0.1:{PORT_METRIQUES}/metrics")
    return res.stdout if res.rc == 0 else ""


def _archives(poste, ip_edge: str, chemin: str, delai: int = 15) -> tuple[int, str, str]:
    """Une requête vers l'instance « archives », avec un jeton propre à la mesure."""
    jeton = secrets.token_hex(5)
    res = poste.run(
        shlex.join(
            [
                "curl",
                "-s",
                "-o",
                "/dev/stdout",
                "-w",
                "\n%{http_code}",
                "--max-time",
                str(delai),
                f"http://{ip_edge}:{PORT_ARCHIVES}{chemin}?t={jeton}",
            ]
        )
    )
    sortie = res.stdout.rsplit("\n", 1)
    corps = sortie[0] if len(sortie) == 2 else ""
    code = int(sortie[-1]) if sortie[-1].strip().isdigit() else 0
    return code, corps, jeton


def _archives_saines(poste, ip_edge: str) -> tuple[bool, str]:
    """Rejoue la matrice saine deux fois, avec un jeton par mesure."""
    for passage in (1, 2):
        for chemin, marqueur in MATRICE_ARCHIVES:
            code, corps, jeton = _archives(poste, ip_edge, chemin)
            if code != 200 or marqueur not in corps or jeton not in corps:
                return False, (
                    f"passage {passage}, {chemin} : code {code}, "
                    f"attendu 200 avec {marqueur!r} ; reçu {corps.strip()[:80]!r}"
                )
    return True, ""


def _exiger_archives_saines(poste, ip_edge: str) -> None:
    ok, detail = _archives_saines(poste, ip_edge)
    assert ok, message(
        en="The archives instance is not healthy yet, so its safeguards cannot "
        f"be judged: repair the service first ({detail}).",
        fr="L'instance archives n'est pas encore saine, ses protections ne se "
        f"jugent donc pas : réparez d'abord le service ({detail}).",
    )


def _attendre_limite_videe(poste, ip_edge: str) -> None:
    """Laisse retomber la limite de débit qu'une rafale précédente a chargée.

    Le dernier test finit sur une rafale de 80 requêtes vers le catalogue. Un
    contrôle relancé juste après arrivait donc sur un compteur encore plein, et
    le test 02 lisait un 429 qui ne disait rien du service : mesuré le
    2026-10-31, le second passage tombait à 14/20 pour cette seule raison.
    On n'attend que si le catalogue répond 429, et au plus deux fenêtres : un
    429 qui persiste au-delà est un défaut réel, que le test signalera.
    """
    limite = time.monotonic() + 2 * FENETRE_COMPLETE
    while time.monotonic() < limite:
        code, _ = _https(poste, ip_edge, CATALOGUE, f"/?nonce={secrets.token_hex(4)}")
        if code != 429:
            return
        time.sleep(3)


def _exiger_catalogue_publie(poste, ip_edge: str) -> None:
    """Prémisse des tests longs : le catalogue répond en HTTPS strict.

    `dsoxlab check` coupe la suite à 300 s. Avant le travail, un test qui
    dormirait une fenêtre de limitation ou redémarrerait la machine avant de
    constater l'absence du service ferait dépasser ce délai, et la suite
    entière serait perdue au lieu de noter 0. Ces tests vérifient donc d'abord,
    en une requête, qu'il y a un service à juger.
    """
    code, _ = _https(poste, ip_edge, CATALOGUE, f"/api/produits?nonce={secrets.token_hex(4)}")
    assert code == 200, message(
        en=f"https://{CATALOGUE}/api/produits answers {code} under strict TLS: "
        "publish the service first, this guarantee is judged on it.",
        fr=f"https://{CATALOGUE}/api/produits répond {code} sous TLS strict : "
        "publiez d'abord le service, cette garantie se juge sur lui.",
    )


# ---------------------------------------------------------------------------
# 01-04 : publication et protocoles (20 points)
# ---------------------------------------------------------------------------


def test_01_le_cycle_renouvelle_les_deux_certificats(edge, poste) -> None:
    """La validation EXÉCUTE `renouveler` et mesure entre deux appels.

    Un cycle ne se constate pas après coup : un certificat valide ne dit pas
    s'il a été obtenu par un script rejouable ou à la main une fois. Et un
    cycle qui ne se rejoue pas est un certificat qui expirera un jour où
    personne ne regardera.
    """
    avant = {nom: _presente(edge, nom) for nom in NOMS}
    lancement = edge.run(f"sudo {RENOUVELER} 2>&1")
    assert lancement.rc == 0, message(
        en=f"{RENOUVELER} failed (code {lancement.rc}): "
        f"{lancement.stdout.strip()[-300:]!r}",
        fr=f"{RENOUVELER} a échoué (code {lancement.rc}) : "
        f"{lancement.stdout.strip()[-300:]!r}",
    )
    for nom in NOMS:
        apres = _presente(edge, nom)
        assert apres["serial"] != avant[nom]["serial"], message(
            en=f"{nom} still serves serial {apres['serial']} after the script "
            "ran: either no certificate was obtained, or it was written to "
            "disk and never loaded.",
            fr=f"{nom} sert encore le numéro de série {apres['serial']} après "
            "le script : soit aucun certificat n'a été obtenu, soit il a été "
            "écrit sur le disque et jamais chargé.",
        )
        valide = edge.run(
            f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
            f"2>/dev/null | openssl x509 -noout -checkend 120"
        )
        assert valide.rc == 0, message(
            en=f"The certificate served for {nom} right after the cycle expires "
            "within two minutes: the cycle produced stale material.",
            fr=f"Le certificat servi pour {nom} juste après le cycle expire dans "
            "moins de deux minutes : le cycle a produit du matériel périmé.",
        )


def test_02_les_deux_services_repondent_en_https_strict(edge, poste, ip_edge) -> None:
    """Chaque nom atteint SON service, sous vérification stricte, avec un nonce.

    Le nonce est choisi au moment de la requête : une réponse mise en cache ou
    fabriquée ne peut pas le contenir. Et sans la racine de l'autorité de
    test, la requête doit échouer : le certificat n'est pas approuvé d'office.
    """
    _preparer(edge, poste)
    _attendre_limite_videe(poste, ip_edge)
    for nom, service in ((CATALOGUE, "catalogue"), (NOTIFICATIONS, "notifications")):
        nonce = secrets.token_hex(6)
        code, corps = _https(poste, ip_edge, nom, f"/?nonce={nonce}")
        reponse = _json(corps)
        assert code == 200, message(
            en=f"https://{nom}/ returns {code}, not 200 under strict TLS "
            "validation (chain and name).",
            fr=f"https://{nom}/ répond {code}, pas 200, sous vérification TLS "
            "stricte (chaîne et nom).",
        )
        assert reponse.get("service") == service, message(
            en=f"https://{nom}/ is served by {reponse.get('service')!r}, not "
            f"{service!r}: the routing sends this name to the wrong backend.",
            fr=f"https://{nom}/ est servi par {reponse.get('service')!r}, pas "
            f"par {service!r} : le routage envoie ce nom vers le mauvais backend.",
        )
        assert reponse.get("nonce") == nonce, message(
            en="The response does not echo the nonce chosen for this request: "
            "it may be cached or faked rather than really served.",
            fr="La réponse ne renvoie pas le nonce choisi pour cette requête : "
            "elle pourrait être en cache ou simulée plutôt que réellement servie.",
        )
        sans = poste.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 8 "
            f"--resolve {nom}:443:{ip_edge} https://{nom}/ 2>&1"
        )
        assert sans.stdout.strip() != "200", message(
            en=f"https://{nom}/ succeeds without the test authority in the trust "
            "store: the validation is not really strict.",
            fr=f"https://{nom}/ aboutit sans l'autorité de test dans le magasin "
            "de confiance : la validation n'est pas réellement stricte.",
        )


def test_03_nom_inconnu_refuse_et_http_redirige(edge, poste, ip_edge) -> None:
    """Un nom que personne n'a déclaré n'atteint aucun service ; HTTP redirige."""
    _preparer(edge, poste)
    code, corps = _https(
        poste, ip_edge, CATALOGUE, "/", entetes=("Host: inconnu.epreuve.test",)
    )
    assert code >= 400 and '"service"' not in corps, message(
        en=f"A request for an unknown name (code {code}) reaches a service. A "
        "name nobody declared must be refused before any backend.",
        fr=f"Une requête pour un nom inconnu (code {code}) atteint un service. "
        "Un nom que personne n'a déclaré doit être refusé avant tout backend.",
    )
    for nom in NOMS:
        res = poste.run(
            f"curl -s -o /dev/null -w '%{{http_code}} %{{redirect_url}}' "
            f"--max-time 8 --resolve {nom}:80:{ip_edge} 'http://{nom}/x?y=1'"
        )
        morceaux = res.stdout.strip().split(" ", 1)
        redirige = (
            morceaux[0] in {"301", "302", "303", "307", "308"}
            and len(morceaux) == 2
            and morceaux[1].startswith(f"https://{nom}")
        )
        assert redirige, message(
            en=f"http://{nom}/ answers {res.stdout.strip()!r}: port 80 must "
            "redirect to https://, apart from the ACME challenge.",
            fr=f"http://{nom}/ répond {res.stdout.strip()!r} : le port 80 doit "
            "rediriger vers https://, hors défi ACME.",
        )


def test_04_un_materiel_invalide_est_refuse_sans_couper_le_service(
    edge, poste, ip_edge
) -> None:
    """Un chargement vérifié refuse du matériel cassé et garde le précédent.

    Un `systemctl restart` après chaque renouvellement charge aussi le nouveau
    matériel : il passerait le test de cycle. La différence est qu'il coupe les
    connexions en cours, et que sur un matériel cassé il laisse le service à
    terre, là où `commit ssl cert` refuse et garde le certificat en service.
    """
    _preparer(edge, poste)
    liste = edge.run(f"echo 'show ssl cert' | sudo socat -t5 stdio {SOCKET} 2>&1")
    chemins = [
        ligne.strip().lstrip("*")
        for ligne in liste.stdout.splitlines()
        if ligne.strip().lstrip("*").startswith("/")
    ]
    assert chemins, message(
        en=f"`show ssl cert` on {SOCKET} lists no certificate "
        f"(answer: {liste.stdout.strip()[:120]!r}): the runtime socket is "
        "missing or serves nothing.",
        fr=f"`show ssl cert` sur {SOCKET} ne liste aucun certificat "
        f"(réponse : {liste.stdout.strip()[:120]!r}) : le socket d'exécution "
        "est absent ou ne sert rien.",
    )
    chemin = chemins[0]
    avant = {nom: _presente(edge, nom)["serial"] for nom in NOMS}

    charge = "-----BEGIN CERTIFICATE-----\npas un certificat\n-----END CERTIFICATE-----"
    pousse = edge.run(
        f"printf 'set ssl cert {chemin} <<\n{charge}\n\n' "
        f"| sudo socat -t5 stdio {SOCKET} 2>&1"
    )
    try:
        commit = edge.run(
            f"echo 'commit ssl cert {chemin}' | sudo socat -t5 stdio {SOCKET} 2>&1"
        )
        sorties = (pousse.stdout + commit.stdout).lower()
        refuse = commit.rc != 0 or any(
            motif in sorties
            for motif in ("error", "erreur", "unable", "cannot", "invalid", "fail")
        )
        assert refuse, message(
            en="Invalid certificate material was accepted without a word "
            f"(answers: {pousse.stdout.strip()[:100]!r} then "
            f"{commit.stdout.strip()[:100]!r}). A verified load checks the "
            "material before putting it into service.",
            fr="Du matériel de certificat invalide a été accepté sans un mot "
            f"(réponses : {pousse.stdout.strip()[:100]!r} puis "
            f"{commit.stdout.strip()[:100]!r}). Un chargement vérifié contrôle "
            "le matériel avant de le mettre en service.",
        )
    finally:
        edge.run(f"echo 'abort ssl cert {chemin}' | sudo socat -t5 stdio {SOCKET}")

    for nom in NOMS:
        assert _presente(edge, nom)["serial"] == avant[nom], message(
            en=f"{nom} no longer serves the certificate it served before the "
            "invalid material was pushed: a refusal must leave the running "
            "certificate in place.",
            fr=f"{nom} ne sert plus le certificat qu'il servait avant que le "
            "matériel invalide ne soit poussé : un refus doit laisser en place "
            "le certificat en service.",
        )
    code, _ = _https(poste, ip_edge, CATALOGUE, "/")
    assert code == 200, message(
        en="The catalogue no longer answers after an invalid certificate was "
        "refused: refusing must not take the service with it.",
        fr="Le catalogue ne répond plus après le refus d'un certificat invalide :"
        " refuser ne doit pas emporter le service.",
    )


# ---------------------------------------------------------------------------
# 05-09 : sécurité et confiance (25 points)
# ---------------------------------------------------------------------------


def test_05_services_et_ecoutes_ne_sortent_pas_du_point_d_entree(
    edge, poste, ip_edge
) -> None:
    """Les backends ne répondent qu'à la machine ; rien d'autre n'écoute dehors.

    La partie « le service marche toujours en local » est la moitié qui compte :
    sans elle, arrêter les backends fermerait le port et passerait le contrôle.
    Les services démarrent sur toutes les interfaces : les fermer est un geste
    de l'apprenant, donc ce test est rouge avant le travail.
    """
    ouverts = [p for p in PORTS_BACKENDS if _port_ouvert(poste, ip_edge, p)]
    assert not ouverts, message(
        en=f"Backend ports {ouverts} accept connections from the client "
        "network: the entry point can be bypassed.",
        fr=f"Les ports de backend {ouverts} acceptent des connexions depuis le "
        "réseau du client : le point d'entrée peut être contourné.",
    )
    for port in PORTS_BACKENDS:
        local = edge.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
            f"http://127.0.0.1:{port}/pret"
        )
        assert local.stdout.strip() == "200", message(
            en=f"The backend on 127.0.0.1:{port} no longer answers on the "
            "machine itself: closing it to the network must not stop it.",
            fr=f"Le backend sur 127.0.0.1:{port} ne répond plus sur la machine "
            "elle-même : le fermer au réseau ne doit pas l'arrêter.",
        )
    ecoutes = edge.run("ss -H -ltn").stdout
    exposes: set[int] = set()
    for ligne in ecoutes.splitlines():
        champs = ligne.split()
        if len(champs) < 4:
            continue
        adresse, _, port = champs[3].rpartition(":")
        if adresse.startswith(("127.", "[::1]")) or not port.isdigit():
            continue
        exposes.add(int(port))
    en_trop = sorted(exposes - PORTS_AUTORISES)
    assert not en_trop, message(
        en=f"Ports {en_trop} listen beyond the loopback. Only 22, 80, 443 and "
        f"{PORT_ARCHIVES} may: administration and metrics stay on the machine.",
        fr=f"Les ports {en_trop} écoutent au-delà de la boucle locale. Seuls 22, "
        f"80, 443 et {PORT_ARCHIVES} le peuvent : l'administration et les "
        "métriques restent sur la machine.",
    )


def test_06_l_administration_exige_une_identite(edge, poste, ip_edge) -> None:
    """Refus sans identité, malgré des en-têtes forgés ; accès avec la bonne.

    Les deux moitiés comptent : un proxy qui refuserait tout validerait les
    refus en retirant le service. Et le backend ne protège RIEN lui-même, donc
    une règle écrite pour `/admin/` seul laisse passer `/admin`.
    """
    _preparer(edge, poste)
    forges = ("X-Forwarded-For: 127.0.0.1", "X-Real-IP: 127.0.0.1")
    for nom in NOMS:
        for chemin in ("/admin", "/admin/", "/admin/utilisateurs"):
            for entetes, auth in (((), None), (forges, None), ((), "ops:mauvais")):
                code, corps = _https(
                    poste, ip_edge, nom, chemin, entetes=entetes, auth=auth
                )
                assert code in (401, 403) and '"administration"' not in corps, message(
                    en=f"https://{nom}{chemin} answers {code} to a caller with "
                    f"no valid identity (headers {entetes}, credentials "
                    f"{auth!r}): administration must be refused.",
                    fr=f"https://{nom}{chemin} répond {code} à un appelant sans "
                    f"identité valide (en-têtes {entetes}, identifiants "
                    f"{auth!r}) : l'administration doit être refusée.",
                )
        code, corps = _https(poste, ip_edge, nom, "/admin/", auth=ADMIN)
        assert code == 200 and _json(corps).get("administration") is True, message(
            en=f"https://{nom}/admin/ with the right credentials answers {code}: "
            "the administration must stay reachable by whoever holds them.",
            fr=f"https://{nom}/admin/ avec les bons identifiants répond {code} : "
            "l'administration doit rester accessible à qui les détient.",
        )
    code, _ = _https(poste, ip_edge, CATALOGUE, f"/api/produits?nonce={secrets.token_hex(4)}")
    assert code == 200, message(
        en=f"The public route /api/produits answers {code}: protecting "
        "administration must not close the rest.",
        fr=f"La route publique /api/produits répond {code} : protéger "
        "l'administration ne doit pas fermer le reste.",
    )


def test_07_le_client_ne_choisit_pas_son_adresse(edge, poste, ip_edge, ip_poste) -> None:
    """Un en-tête envoyé par le client n'arrive pas au service comme une vérité.

    Le service renvoie TOUTES les occurrences de `X-Forwarded-For` : une
    application qui lit la première voit sinon l'adresse que le client a
    choisie. La moitié qui compte est l'adresse réelle, qui doit arriver :
    supprimer l'en-tête partout passerait la première moitié seule.
    """
    _preparer(edge, poste)
    nonce = secrets.token_hex(6)
    code, corps = _https(
        poste,
        ip_edge,
        CATALOGUE,
        f"/?nonce={nonce}",
        entetes=(f"X-Forwarded-For: {ADRESSE_FORGEE}", "X-Forwarded-Proto: http"),
    )
    reponse = _json(corps)
    assert code == 200 and reponse.get("nonce") == nonce, message(
        en=f"The catalogue answers {code} to a request carrying forged headers.",
        fr=f"Le catalogue répond {code} à une requête portant des en-têtes forgés.",
    )
    adresses = [a.strip() for a in str(reponse.get("xff", "")).split(",")]
    assert ADRESSE_FORGEE not in adresses, message(
        en=f"The service receives X-Forwarded-For {reponse.get('xff')!r}: the "
        "address the client chose reaches the application.",
        fr=f"Le service reçoit X-Forwarded-For {reponse.get('xff')!r} : "
        "l'adresse choisie par le client atteint l'application.",
    )
    assert ip_poste in adresses, message(
        en=f"The service never receives the real client address {ip_poste} "
        f"(X-Forwarded-For: {reponse.get('xff')!r}).",
        fr=f"Le service ne reçoit jamais l'adresse réelle du client {ip_poste} "
        f"(X-Forwarded-For : {reponse.get('xff')!r}).",
    )
    assert reponse.get("proto") == "https", message(
        en=f"The service receives X-Forwarded-Proto {reponse.get('proto')!r} "
        "instead of https: the original protocol is lost or forged.",
        fr=f"Le service reçoit X-Forwarded-Proto {reponse.get('proto')!r} au lieu "
        "de https : le protocole d'origine est perdu ou forgé.",
    )


def test_08_la_limite_par_source_se_declenche_et_se_relache(edge, poste, ip_edge) -> None:
    """Au-delà de 30 requêtes en 10 s par adresse source : 429, puis retour.

    La clé de comptage est mesurée : chaque requête de la rafale porte un
    `X-Forwarded-For` DIFFÉRENT. Une table qui compterait cet en-tête ne
    verrait jamais le dépassement. Et la limite se RELÂCHE : un blocage qui ne
    se lève pas est une interdiction, pas une limite.
    """
    racine = _preparer(edge, poste, marge=200)
    _exiger_catalogue_publie(poste, ip_edge)
    time.sleep(FENETRE_COMPLETE)
    moderes = _rafale(poste, ip_edge, 443, CATALOGUE, "/api/produits", 20, racine)
    assert moderes.count("200") == 20, message(
        en=f"A moderate client (20 requests) is not served in full: {moderes}. "
        "The limit must not touch normal use.",
        fr=f"Un client modéré (20 requêtes) n'est pas servi en entier : {moderes}. "
        "La limite ne doit pas gêner un usage normal.",
    )
    time.sleep(FENETRE_COMPLETE)
    rafale = _rafale(poste, ip_edge, 443, CATALOGUE, "/api/produits", 80, racine)
    assert rafale.count("429") >= 20 and rafale.count("200") >= 15, message(
        en=f"A burst of 80 requests gets {rafale.count('200')} x 200 and "
        f"{rafale.count('429')} x 429. Expected a first batch served, then 429 "
        "beyond 30 requests per 10 s per source address, whatever "
        "X-Forwarded-For says.",
        fr=f"Une rafale de 80 requêtes obtient {rafale.count('200')} x 200 et "
        f"{rafale.count('429')} x 429. Attendu : un premier lot servi, puis des "
        "429 au-delà de 30 requêtes par 10 s et par adresse source, quoi que "
        "dise X-Forwarded-For.",
    )
    time.sleep(FENETRE_COMPLETE)
    code, _ = _https(poste, ip_edge, CATALOGUE, f"/api/produits?nonce={secrets.token_hex(4)}")
    assert code == 200, message(
        en=f"{FENETRE_COMPLETE} seconds after the burst, the catalogue still "
        f"answers {code}: a rate limit releases, it does not ban.",
        fr=f"{FENETRE_COMPLETE} secondes après la rafale, le catalogue répond "
        f"encore {code} : une limite de débit se relâche, elle ne bannit pas.",
    )


def test_09_les_cles_privees_sont_protegees_et_absentes_des_sorties(edge) -> None:
    """Une clé dans un journal est une clé publiée.

    La rotation ne la rattrape pas : le journal est collecté, archivé, recopié
    dans un rapport d'incident, et la clé y reste après l'expiration du
    certificat. Le test exige d'abord qu'il existe un matériel à protéger.
    """
    porteurs = edge.run(
        f"sudo grep -rlE 'PRIVATE[ ]KEY' {WORK}/acme /etc/haproxy 2>/dev/null"
    ).stdout.split()
    assert porteurs, message(
        en=f"No file carrying a private key was found under {WORK}/acme or "
        "/etc/haproxy: either nothing was obtained, or the material lives "
        "somewhere the recipe does not describe.",
        fr=f"Aucun fichier portant une clé privée n'a été trouvé sous {WORK}/acme "
        "ni /etc/haproxy : soit rien n'a été obtenu, soit le matériel vit "
        "ailleurs que là où la recette le décrit.",
    )
    for chemin in porteurs:
        droits = edge.run(f"sudo stat -c '%a' {chemin}").stdout.split()
        assert droits and int(droits[0], 8) & 0o007 == 0, message(
            en=f"{chemin} carries a private key and is mode "
            f"{droits[0] if droits else '?'}: any account on the machine can "
            "read it.",
            fr=f"{chemin} porte une clé privée et est en mode "
            f"{droits[0] if droits else '?'} : n'importe quel compte de la "
            "machine peut la lire.",
        )
    dans_les_logs = edge.run(
        "sudo grep -rlE 'PRIVATE[ ]KEY' /var/log 2>/dev/null"
    ).stdout.split()
    assert not dans_les_logs, message(
        en=f"A private key appears in {dans_les_logs}.",
        fr=f"Une clé privée apparaît dans {dans_les_logs}.",
    )
    dans_le_journal = edge.run(
        "sudo journalctl -b --no-pager 2>/dev/null | grep -cE 'PRIVATE[ ]KEY'"
    ).stdout.strip()
    assert dans_le_journal in ("", "0"), message(
        en=f"The system journal carries {dans_le_journal} lines with private key "
        "material: a renewal script must never print what it writes.",
        fr=f"Le journal système porte {dans_le_journal} lignes de matériel de clé "
        "privée : un script de renouvellement n'imprime jamais ce qu'il écrit.",
    )


# ---------------------------------------------------------------------------
# 10-13 : observabilité et flux (20 points)
# ---------------------------------------------------------------------------


def test_10_le_flux_long_arrive_entier(edge, poste, ip_edge) -> None:
    """Un flux d'événements espacés de 35 s dure 75 s sans être coupé.

    Le silence entre deux événements dépasse les bornes d'inactivité courantes
    (30 s) : une borne mal choisie coupe le flux après le premier événement. La
    mesure compte les événements et lit leurs horodatages côté serveur, pour
    qu'un flux simulé par le proxy ne passe pas.
    """
    racine = _preparer(edge, poste, marge=200)
    res = poste.run(
        shlex.join(
            [
                "curl",
                "-sN",
                "--max-time",
                "110",
                "--cacert",
                racine,
                "--resolve",
                f"{NOTIFICATIONS}:443:{ip_edge}",
                f"https://{NOTIFICATIONS}/flux?nonce={secrets.token_hex(4)}",
            ]
        )
    )
    evenements = []
    for ligne in res.stdout.splitlines():
        if ligne.startswith("data:"):
            try:
                evenements.append(json.loads(ligne[5:]))
            except ValueError:
                continue
    assert len(evenements) >= 3, message(
        en=f"The stream delivered {len(evenements)} event(s) instead of 3: it was "
        "cut during the silence between two events. Look at which bound "
        "measures inactivity on a long-lived response.",
        fr=f"Le flux a livré {len(evenements)} événement(s) au lieu de 3 : il a "
        "été coupé pendant le silence entre deux événements. Cherchez quelle "
        "borne mesure l'inactivité sur une réponse de longue durée.",
    )
    ecarts = [
        b["horodatage"] - a["horodatage"] for a, b in itertools.pairwise(evenements)
    ]
    assert all(25 <= ecart <= 50 for ecart in ecarts), message(
        en=f"The events are not spaced by the application's heartbeat (35 s): "
        f"gaps {ecarts}. The stream may be buffered or rebuilt by the proxy.",
        fr=f"Les événements ne sont pas espacés du battement de l'application "
        f"(35 s) : écarts {ecarts}. Le flux est peut-être mis en tampon ou "
        "reconstruit par le proxy.",
    )


def test_11_les_metriques_sont_privees_et_suivent_le_trafic(edge, poste, ip_edge) -> None:
    """Le point de métriques répond sur la machine, nulle part ailleurs, et bouge.

    « Bouge » est la moitié qui compte : un exporteur qui répond sans que ses
    compteurs suivent le trafic réel ne sert à aucune alerte.
    """
    racine = _preparer(edge, poste)
    ouverts = [p for p in (PORT_METRIQUES, 8404) if _port_ouvert(poste, ip_edge, p)]
    assert not ouverts, message(
        en=f"Ports {ouverts} (metrics, statistics) accept connections from the "
        "client network.",
        fr=f"Les ports {ouverts} (métriques, statistiques) acceptent des "
        "connexions depuis le réseau du client.",
    )
    avant = _metriques(edge)
    assert "haproxy_frontend_status" in avant and "haproxy_server_status" in avant, message(
        en=f"http://127.0.0.1:{PORT_METRIQUES}/metrics does not expose the "
        "frontend and server status metrics.",
        fr=f"http://127.0.0.1:{PORT_METRIQUES}/metrics n'expose pas les "
        "métriques d'état des frontends et des serveurs.",
    )
    codes = _rafale(poste, ip_edge, 443, CATALOGUE, "/api/produits", 12, racine)
    assert codes.count("200") == 12, message(
        en=f"The traffic generated for this check was not served: {codes}.",
        fr=f"Le trafic généré pour cette mesure n'a pas été servi : {codes}.",
    )
    apres = _metriques(edge)
    delta = _somme(apres, "haproxy_frontend_http_requests_total") - _somme(
        avant, "haproxy_frontend_http_requests_total"
    )
    assert delta >= 12, message(
        en=f"The request counter grew by {delta} after 12 real requests: the "
        "metrics do not follow the traffic.",
        fr=f"Le compteur de requêtes a progressé de {delta} après 12 requêtes "
        "réelles : les métriques ne suivent pas le trafic.",
    )


def test_12_l_arret_d_un_service_se_lit_dans_les_metriques(edge, poste, ip_edge) -> None:
    """Un service arrêté passe DOWN dans les métriques, puis revient UP.

    C'est le signal qu'une règle d'alerte lirait. Le test arrête réellement le
    service de notifications, attend que le nombre de serveurs DOWN dépasse sa
    valeur de départ, vérifie que le catalogue continue de répondre, puis
    rétablit et exige le retour à la valeur de départ.
    """
    _preparer(edge, poste)
    assert "haproxy_server_status" in _metriques(edge), message(
        en=f"No haproxy_server_status metric on 127.0.0.1:{PORT_METRIQUES}/metrics: "
        "expose the metrics first, the outage is read from them.",
        fr=f"Aucune métrique haproxy_server_status sur 127.0.0.1:{PORT_METRIQUES}/metrics : "
        "exposez d'abord les métriques, la panne se lit dans elles.",
    )
    base = _serveurs_down(_metriques(edge))
    unite = "pub-epreuve-haproxy-notifications.service"
    tombe = False
    try:
        edge.run(f"sudo systemctl stop {unite}")
        limite = time.monotonic() + 60
        while time.monotonic() < limite:
            if _serveurs_down(_metriques(edge)) > base:
                tombe = True
                break
            time.sleep(2)
        assert tombe, message(
            en="Sixty seconds after stopping the notifications service, no "
            "server is reported DOWN in the metrics: the servers have no "
            "health check, or the metrics do not carry their status.",
            fr="Soixante secondes après l'arrêt du service de notifications, "
            "aucun serveur n'est signalé DOWN dans les métriques : les serveurs "
            "n'ont pas de sonde, ou les métriques ne portent pas leur état.",
        )
        code, corps = _https(poste, ip_edge, NOTIFICATIONS, "/")
        assert code >= 500 and '"service": "notifications"' not in corps, message(
            en=f"While notifications is stopped, its name answers {code}: "
            "expected a server error, not another service's answer.",
            fr=f"Pendant l'arrêt de notifications, son nom répond {code} : "
            "attendu une erreur serveur, pas la réponse d'un autre service.",
        )
        code, _ = _https(poste, ip_edge, CATALOGUE, f"/?nonce={secrets.token_hex(4)}")
        assert code == 200, message(
            en=f"The catalogue answers {code} while notifications is down: one "
            "service's failure must not take the other.",
            fr=f"Le catalogue répond {code} pendant la panne de notifications : "
            "la panne d'un service ne doit pas emporter l'autre.",
        )
    finally:
        edge.run(f"sudo systemctl start {unite}")
    retabli = False
    limite = time.monotonic() + 60
    while time.monotonic() < limite:
        if _serveurs_down(_metriques(edge)) <= base:
            retabli = True
            break
        time.sleep(2)
    assert retabli, message(
        en="Sixty seconds after restarting the notifications service, the "
        "metrics still report a server DOWN: the probe does not bring it back.",
        fr="Soixante secondes après le redémarrage de notifications, les "
        "métriques signalent encore un serveur DOWN : la sonde ne le réintègre pas.",
    )
    code, corps = _https(poste, ip_edge, NOTIFICATIONS, f"/?nonce={secrets.token_hex(4)}")
    assert code == 200 and _json(corps).get("service") == "notifications", message(
        en=f"Notifications answers {code} after being restarted.",
        fr=f"Notifications répond {code} après son redémarrage.",
    )


def test_13_les_refus_se_comptent_dans_les_metriques(edge, poste, ip_edge) -> None:
    """Les refus réels (401) augmentent le compteur de réponses 4xx.

    Une alerte sur le taux d'erreurs ne vaut que si les refus du proxy lui-même
    y sont comptés. On génère six refus d'administration et on lit l'écart.
    """
    _preparer(edge, poste)
    avant = _somme(_metriques(edge), "haproxy_frontend_http_responses_total", 'code="4xx"')
    refus = 0
    for _ in range(6):
        code, _corps = _https(poste, ip_edge, CATALOGUE, "/admin/")
        refus += 1 if code in (401, 403) else 0
    assert refus == 6, message(
        en=f"Only {refus}/6 anonymous requests to /admin/ were refused.",
        fr=f"Seulement {refus}/6 requêtes anonymes vers /admin/ ont été refusées.",
    )
    apres = _somme(_metriques(edge), "haproxy_frontend_http_responses_total", 'code="4xx"')
    assert apres - avant >= 6, message(
        en=f"The 4xx response counter grew by {apres - avant} after 6 real "
        "refusals: refusals are not visible in the metrics.",
        fr=f"Le compteur de réponses 4xx a progressé de {apres - avant} après 6 "
        "refus réels : les refus ne sont pas visibles dans les métriques.",
    )


# ---------------------------------------------------------------------------
# 14-17 : diagnostic de la panne (20 points)
# ---------------------------------------------------------------------------


def test_14_le_diagnostic_nomme_la_famille_et_le_composant(edge, secret) -> None:
    """Le champ structuré est comparé au secret ; la prose est lue par un humain.

    Un champ `famille` à valeur fermée est comparé à la famille réellement
    tirée. Le champ `composant` est lu par SIGNAUX NORMALISÉS (minuscules, sans
    accent), jamais par une chaîne exacte. Énumérer toutes les familles « au
    cas où » n'est pas un diagnostic. Le contenu de `explication` est lu par un
    relecteur ; sa seule absence est notée ici.
    """
    res = edge.run(f"cat {INCIDENT_YAML}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{INCIDENT_YAML} does not exist or is empty.",
        fr=f"{INCIDENT_YAML} n'existe pas ou est vide.",
    )
    try:
        diagnostic = yaml.safe_load(res.stdout)
    except yaml.YAMLError:
        diagnostic = None
    assert isinstance(diagnostic, dict), message(
        en=f"{INCIDENT_YAML} is not a YAML mapping (famille / composant / explication).",
        fr=f"{INCIDENT_YAML} n'est pas un dictionnaire YAML (famille / composant / "
        "explication).",
    )
    famille = str(diagnostic.get("famille", "")).strip().lower()
    assert famille in FAMILLES, message(
        en=f"The 'famille' field must be one of {list(FAMILLES)}, got {famille!r}.",
        fr=f"Le champ 'famille' doit valoir l'une de {list(FAMILLES)}, pas {famille!r}.",
    )
    assert famille == secret.get("incident"), message(
        en=f"{INCIDENT_YAML} names the family {famille!r}, but the fault that was "
        "laid is in another one.",
        fr=f"{INCIDENT_YAML} nomme la famille {famille!r}, mais la panne posée est "
        "dans une autre.",
    )
    composant = _normaliser(diagnostic.get("composant", ""))
    assert any(signal in composant for signal in SIGNAUX[famille]), message(
        en="The 'composant' field never names the faulty component (the "
        "directive, the file or the object at fault). The free-text "
        "'explication' is read by a human and is not graded here.",
        fr="Le champ 'composant' ne nomme jamais le composant fautif (la "
        "directive, le fichier ou l'objet en cause). Le texte libre "
        "'explication' est lu par un humain et n'est pas noté ici.",
    )
    etrangeres = [
        autre
        for autre, signaux in SIGNAUX.items()
        if autre != famille and any(signal in composant for signal in signaux)
    ]
    assert len(etrangeres) <= AUTRES_FAMILLES_TOLEREES, message(
        en=f"The 'composant' field also names {etrangeres}: listing several "
        "families is not a diagnosis. Ruled-out hypotheses belong in "
        "'explication'.",
        fr=f"Le champ 'composant' nomme aussi {etrangeres} : citer plusieurs "
        "familles n'est pas un diagnostic. Les hypothèses écartées ont leur "
        "place dans 'explication'.",
    )
    assert str(diagnostic.get("explication", "")).strip(), message(
        en=f"{INCIDENT_YAML} carries no 'explication'. Its content is read by a "
        "human reviewer and is not graded here, but its absence is.",
        fr=f"{INCIDENT_YAML} ne porte aucune 'explication'. Son contenu est lu "
        "par un relecteur humain et n'est pas noté ici, mais son absence l'est.",
    )


def test_15_le_service_archives_est_repare(poste, ip_edge) -> None:
    """La matrice saine est rejouée deux fois, avec un jeton par mesure."""
    ok, detail = _archives_saines(poste, ip_edge)
    assert ok, message(
        en=f"The archives instance does not serve its healthy matrix: {detail}.",
        fr=f"L'instance archives ne sert pas sa matrice saine : {detail}.",
    )


def test_16_la_confiance_et_la_sonde_sont_conservees(poste, ip_edge) -> None:
    """Réparer ne retire ni la vérification TLS ni les sondes.

    Deux canaris font partie de l'état sain. `/usurpe/` mène à un backend de
    même nom dont le certificat est signé par une autorité étrangère : sa
    réponse porte le même marqueur que le légitime, donc elle est
    indiscernable d'un succès si la vérification est désactivée. Le serveur
    `degrade` est vivant, en échec : il ne reste hors service que tant que les
    sondes tournent. `verify none` et le retrait des sondes font repartir le
    service dans deux familles de pannes, et retirent la garantie en même temps.

    Le test exige d'abord le service réparé : ces deux garanties sont vraies
    sur l'état de départ, elles ne comptent donc qu'une fois le travail fait.
    """
    _exiger_archives_saines(poste, ip_edge)
    time.sleep(FENETRE_COMPLETE)
    for _ in range(3):
        code, corps, _jeton = _archives(poste, ip_edge, "/usurpe/")
        assert code != 200 and "archives-api" not in corps, message(
            en=f"/usurpe/ answers {code} with the legitimate backend's marker: "
            "the TLS verification toward backends is no longer strict.",
            fr=f"/usurpe/ répond {code} avec le marqueur du backend légitime : la "
            "vérification TLS vers les backends n'est plus stricte.",
        )
    codes = _rafale(poste, ip_edge, PORT_ARCHIVES, "archives", "/", 30)
    assert codes.count("200") == 30, message(
        en=f"Among 30 requests to '/', {30 - codes.count('200')} were not "
        f"served 200 ({sorted(set(codes))}): the failing server is back in "
        "service, so the health probes are gone.",
        fr=f"Sur 30 requêtes vers '/', {30 - codes.count('200')} n'ont pas reçu "
        f"200 ({sorted(set(codes))}) : le serveur en échec est revenu en "
        "service, donc les sondes ont disparu.",
    )


def test_17_la_limite_de_debit_et_la_borne_d_attente_sont_conservees(poste, ip_edge) -> None:
    """Réparer ne désarme ni la limite de débit ni la borne de réponse.

    Une limite qu'on relève à l'infini et une borne qu'on étire jusqu'à la durée
    de la route bloquée rétablissent le service et retirent la protection. La
    route `/v2/bloque` met 25 s à répondre : l'état sain la coupe en 504 bien
    avant. Le test exige d'abord le service réparé, parce que ces deux
    garanties sont vraies sur l'état de départ des autres familles de pannes.
    """
    _exiger_archives_saines(poste, ip_edge)
    time.sleep(FENETRE_COMPLETE)
    codes = _rafale(poste, ip_edge, PORT_ARCHIVES, "archives", "/", 300)
    assert "429" in codes, message(
        en="300 requests in a few seconds never meet a 429: the rate limit is "
        "gone or set so high that it protects nothing.",
        fr="300 requêtes en quelques secondes ne rencontrent jamais de 429 : la "
        "limite de débit a disparu, ou son seuil est si haut qu'elle ne protège "
        "plus rien.",
    )
    time.sleep(FENETRE_COMPLETE)
    debut = time.monotonic()
    code, _corps, _jeton = _archives(poste, ip_edge, "/v2/bloque", delai=40)
    duree = time.monotonic() - debut
    assert code == 504 and duree <= 20, message(
        en=f"A response blocked for 25 s ends with code {code} after "
        f"{duree:.0f} s. Expected a 504 within 20 s: the wait bound on the "
        "server was lifted instead of fixed.",
        fr=f"Une réponse bloquée 25 s se termine avec le code {code} après "
        f"{duree:.0f} s. Attendu : un 504 en moins de 20 s. La borne d'attente "
        "du serveur a été levée au lieu d'être corrigée.",
    )


# ---------------------------------------------------------------------------
# 18-20 : reprise et retour arrière (15 points)
# ---------------------------------------------------------------------------


def test_18_la_restauration_remet_les_donnees_et_la_configuration(
    edge, poste, ip_edge
) -> None:
    """Sinistre réel : HAProxy arrêté, configuration corrompue, donnée supprimée.

    Le script `restaurer` de l'apprenant est EXÉCUTÉ. Il doit remettre la donnée
    du catalogue et la configuration de HAProxy depuis les sauvegardes, puis
    remettre HAProxy en service, sans toucher aux certificats ni aux
    sauvegardes. Le résultat est jugé sur ce que le service répond, depuis le
    client, avec un nonce neuf et la valeur métier sauvegardée.
    """
    assert edge.run(f"test -s {SAUVEGARDE_CFG}").rc == 0, message(
        en=f"{SAUVEGARDE_CFG} is missing or empty: deposit the backup of your "
        "HAProxy configuration there before the restore can be exercised.",
        fr=f"{SAUVEGARDE_CFG} est absent ou vide : déposez-y la sauvegarde de "
        "votre configuration HAProxy avant que la restauration puisse être "
        "éprouvée.",
    )
    assert edge.run(f"haproxy -c -q -f {SAUVEGARDE_CFG}").rc == 0, message(
        en=f"{SAUVEGARDE_CFG} is not a valid configuration: a backup that does "
        "not load is not a backup.",
        fr=f"{SAUVEGARDE_CFG} n'est pas une configuration valide : une "
        "sauvegarde qui ne se charge pas n'est pas une sauvegarde.",
    )
    _preparer(edge, poste, marge=200)
    valeur = json.loads(edge.run(f"cat {SAUVEGARDE_DONNEES}").stdout)["valeur"]
    empreintes = edge.run(f"sha256sum {SAUVEGARDE_DONNEES} {SAUVEGARDE_CFG}").stdout

    edge.run("sudo systemctl stop haproxy")
    edge.run("printf 'ligne invalide pour haproxy\\n' | sudo tee -a /etc/haproxy/haproxy.cfg")
    edge.run(f"sudo rm -f {DONNEES}")
    assert edge.run("haproxy -c -q -f /etc/haproxy/haproxy.cfg").rc != 0, (
        "banc : la configuration corrompue devrait être refusée par haproxy -c"
    )

    lancement = edge.run(f"sudo {RESTAURER} 2>&1")
    assert lancement.rc == 0, message(
        en=f"{RESTAURER} failed (code {lancement.rc}): "
        f"{lancement.stdout.strip()[-300:]!r}",
        fr=f"{RESTAURER} a échoué (code {lancement.rc}) : "
        f"{lancement.stdout.strip()[-300:]!r}",
    )
    assert edge.run("haproxy -c -q -f /etc/haproxy/haproxy.cfg").rc == 0, message(
        en="After the restore, /etc/haproxy/haproxy.cfg is still not a valid "
        "configuration.",
        fr="Après la restauration, /etc/haproxy/haproxy.cfg n'est toujours pas "
        "une configuration valide.",
    )
    assert edge.run(f"cmp /etc/haproxy/haproxy.cfg {SAUVEGARDE_CFG}").rc == 0, message(
        en="After the restore, /etc/haproxy/haproxy.cfg differs from the backup.",
        fr="Après la restauration, /etc/haproxy/haproxy.cfg diffère de la "
        "sauvegarde.",
    )
    limite = time.monotonic() + 45
    code, corps, nonce = 0, "", ""
    while time.monotonic() < limite:
        nonce = secrets.token_hex(6)
        code, corps = _https(
            poste, ip_edge, CATALOGUE, f"/api/produits?nonce={nonce}", avec_racine=True
        )
        if code == 200:
            break
        time.sleep(3)
    reponse = _json(corps)
    assert code == 200 and reponse.get("nonce") == nonce, message(
        en=f"After the restore, https://{CATALOGUE}/api/produits answers {code}: "
        "the restore did not bring the service back (HAProxy running again, "
        "business data in place).",
        fr=f"Après la restauration, https://{CATALOGUE}/api/produits répond "
        f"{code} : la restauration n'a pas remis le service en marche (HAProxy "
        "relancé, donnée métier en place).",
    )
    assert reponse.get("valeur") == valeur, message(
        en=f"After the restore the service answers valeur={reponse.get('valeur')!r}, "
        f"not the backed up {valeur!r}: the data restore did not use the backup.",
        fr=f"Après la restauration le service répond valeur={reponse.get('valeur')!r},"
        f" pas la valeur sauvegardée {valeur!r} : la restauration des données "
        "n'a pas utilisé la sauvegarde.",
    )
    apres = edge.run(f"sha256sum {SAUVEGARDE_DONNEES} {SAUVEGARDE_CFG}").stdout
    assert apres == empreintes, message(
        en="The backups were modified by the restore: a restore reads them, it "
        "never rewrites them.",
        fr="Les sauvegardes ont été modifiées par la restauration : une "
        "restauration les lit, elle ne les réécrit jamais.",
    )


def test_19_un_rechargement_ne_coupe_pas_le_service(edge, poste, ip_edge) -> None:
    """`reload` sous trafic : au plus une requête perdue, et le maître reste.

    Un redémarrage au lieu d'un rechargement change le PID du maître et coupe
    des connexions. Vingt requêtes espacées de 500 ms traversent le
    rechargement ; la sonde passe par le nom de notifications, hors de la
    limite de débit du catalogue.
    """
    racine = _preparer(edge, poste, marge=200)
    pid_avant = edge.run("systemctl show -p MainPID --value haproxy").stdout.strip()
    assert pid_avant not in ("", "0"), message(
        en="HAProxy is not running as a systemd service named haproxy.",
        fr="HAProxy ne tourne pas comme service systemd nommé haproxy.",
    )
    resultat: dict[str, list[str]] = {}

    def sonder() -> None:
        resultat["codes"] = _rafale(
            poste, ip_edge, 443, NOTIFICATIONS, "/", 20, racine, 0.5
        )

    fil = threading.Thread(target=sonder)
    fil.start()
    time.sleep(2)
    recharge = edge.run("sudo systemctl reload haproxy")
    fil.join(90)
    assert recharge.rc == 0, message(
        en=f"`systemctl reload haproxy` failed: {recharge.stdout.strip()[:200]!r}",
        fr=f"`systemctl reload haproxy` a échoué : {recharge.stdout.strip()[:200]!r}",
    )
    codes = resultat.get("codes", [])
    echecs = [c for c in codes if c != "200"]
    assert len(codes) == 20 and len(echecs) <= 1, message(
        en=f"During the reload, {len(echecs)} of {len(codes)} probe requests "
        f"failed ({sorted(set(codes))}). A reload must not interrupt the service.",
        fr=f"Pendant le rechargement, {len(echecs)} requêtes de sonde sur "
        f"{len(codes)} ont échoué ({sorted(set(codes))}). Un rechargement ne doit "
        "pas interrompre le service.",
    )
    pid_apres = edge.run("systemctl show -p MainPID --value haproxy").stdout.strip()
    assert pid_apres == pid_avant, message(
        en=f"The master process changed ({pid_avant} then {pid_apres}): that is a "
        "restart, not a reload.",
        fr=f"Le processus maître a changé ({pid_avant} puis {pid_apres}) : c'est "
        "un redémarrage, pas un rechargement.",
    )


def test_20_le_service_et_ses_garanties_survivent_au_redemarrage(
    edge, poste, ip_edge
) -> None:
    """DERNIER test, parce qu'il coupe la machine. Il rejoue la recette ensuite.

    Après le redémarrage, tout doit revenir SEUL : HAProxy, les services, la
    plateforme de test. La validation remet l'autorité de test à plat (elle
    oublie ses comptes et change de racine à chaque démarrage, ce que ne fait
    pas une vraie autorité), rejoue le cycle de renouvellement de l'apprenant,
    puis vérifie à nouveau la publication, le contrôle d'accès, la fermeture des
    backends et des métriques, et la limite de débit.
    """
    _preparer(edge, poste, marge=200)
    _exiger_catalogue_publie(poste, ip_edge)
    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)
    assert _attendre_retour(edge, 240), message(
        en="edge.lab did not come back online within 240 s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 240 s après le redémarrage.",
    )

    pret = False
    limite = time.monotonic() + 180
    while time.monotonic() < limite:
        ecoutes = edge.run("ss -ltn 'sport = :443'").stdout
        annuaire = edge.run(
            "curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "
            "https://localhost:14000/dir"
        ).stdout.strip()
        if "LISTEN" in ecoutes and annuaire == "200":
            pret = True
            break
        time.sleep(5)
    assert pret, message(
        en="After the reboot, either HAProxy does not listen on 443 or the test "
        "authority does not answer. The service must come back by itself.",
        fr="Après le redémarrage, soit HAProxy n'écoute pas sur le 443, soit "
        "l'autorité de test ne répond pas. Le service doit revenir de lui-même.",
    )

    # L'autorité de test repart vierge : racine neuve, comptes oubliés.
    racine_neuve = edge.run("curl -sk --max-time 8 https://localhost:15000/roots/0").stdout
    edge.run(f"printf '%s\\n' {shlex.quote(racine_neuve.strip())} | sudo tee {WORK}/pebble-root.pem {WORK}/acme/pebble-root.pem >/dev/null")
    edge.run(f"sudo rm -rf {WORK}/acme/accounts")
    lancement = edge.run(f"sudo {RENOUVELER} 2>&1")
    assert lancement.rc == 0, message(
        en="The renewal script fails after the reboot "
        f"(code {lancement.rc}): {lancement.stdout.strip()[-300:]!r}. The cycle "
        "must work again once the machine is back.",
        fr="Le script de renouvellement échoue après le redémarrage "
        f"(code {lancement.rc}) : {lancement.stdout.strip()[-300:]!r}. Le cycle "
        "doit fonctionner de nouveau une fois la machine revenue.",
    )
    racine = _racine_courante(edge, poste)

    for nom, service in ((CATALOGUE, "catalogue"), (NOTIFICATIONS, "notifications")):
        nonce = secrets.token_hex(6)
        code, corps = _https(poste, ip_edge, nom, f"/?nonce={nonce}")
        reponse = _json(corps)
        assert code == 200 and reponse.get("service") == service and reponse.get("nonce") == nonce, message(
            en=f"After the reboot, https://{nom}/ answers {code} "
            f"(service {reponse.get('service')!r}).",
            fr=f"Après le redémarrage, https://{nom}/ répond {code} "
            f"(service {reponse.get('service')!r}).",
        )
        code, _ = _https(poste, ip_edge, nom, "/admin/")
        assert code in (401, 403), message(
            en=f"After the reboot, https://{nom}/admin/ answers {code} to an "
            "anonymous caller: the access control did not persist.",
            fr=f"Après le redémarrage, https://{nom}/admin/ répond {code} à un "
            "appelant anonyme : le contrôle d'accès n'a pas persisté.",
        )
    ouverts = [
        p for p in (*PORTS_BACKENDS, PORT_METRIQUES) if _port_ouvert(poste, ip_edge, p)
    ]
    assert not ouverts, message(
        en=f"After the reboot, ports {ouverts} accept connections from the "
        "client network: the isolation did not persist.",
        fr=f"Après le redémarrage, les ports {ouverts} acceptent des connexions "
        "depuis le réseau du client : l'isolement n'a pas persisté.",
    )
    assert "haproxy_server_status" in _metriques(edge), message(
        en="After the reboot, the metrics endpoint no longer answers on the machine.",
        fr="Après le redémarrage, le point de métriques ne répond plus sur la machine.",
    )
    time.sleep(FENETRE_COMPLETE)
    rafale = _rafale(poste, ip_edge, 443, CATALOGUE, "/api/produits", 80, racine)
    assert rafale.count("429") >= 20, message(
        en=f"After the reboot, a burst of 80 requests gets {rafale.count('429')} "
        "x 429: the rate limit did not persist.",
        fr=f"Après le redémarrage, une rafale de 80 requêtes obtient "
        f"{rafale.count('429')} x 429 : la limite de débit n'a pas persisté.",
    )
