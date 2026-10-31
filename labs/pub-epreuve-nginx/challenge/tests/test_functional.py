"""Épreuve Nginx : publier et exploiter un service.

Cinq points sont mesurés, et chacun l'est sur l'ÉTAT RÉEL du banc, jamais sur
la forme d'un fichier :

  publication   le bon contenu par nom, un TLS strict, un renouvellement qui
                met réellement une nouvelle série en service ;
  politique     la matrice de refus, l'origine inaccessible, un cache qui ne
                mélange jamais deux sessions ;
  operation     un flux livré au rythme du backend, un journal dont les durées
                mesurent, un point d'état local, une alerte qui se déclenche
                puis se résout ;
  incident      un incident non annoncé, posé APRÈS la recette initiale, tiré
                au sort parmi quatre variantes, diagnostiqué puis corrigé sans
                perdre aucune garantie ;
  reprise       une sauvegarde, une destruction, une restauration, puis un
                redémarrage de la machine et la recette complète rejouée.

DEUX RÈGLES QUI TRAVERSENT CE FICHIER

1. Aucun test n'est vert avant le travail. Le banc ne sert rien : sans la
   configuration de l'apprenant, aucune requête n'aboutit, donc aucune
   assertion ne peut passer. Les protections que le banc pose lui-même (le
   backend n'écoute que sur la boucle locale) sont fondues dans des tests qui
   exigent aussi du travail, jamais comptées seules.

2. Le diagnostic de l'incident se compare au secret tiré au sort, par SIGNAUX
   NORMALISÉS : on retire les accents et la ponctuation, puis on cherche des
   familles de mots, jamais une chaîne exacte. Un champ `composant` qui cite
   une autre variante que la vraie est refusé, parce que tout nommer à la fois
   n'est pas un diagnostic ; les hypothèses écartées ont leur place dans
   `explication`, qui est lue par un relecteur et non notée.

LE DERNIER TEST COUPE LA MACHINE, et il est donc placé en dernier.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import shlex
import time
import unicodedata

import pytest
import yaml

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
WWW = "www.epreuve.test"
API = "api.epreuve.test"
NOMS = (WWW, API)
WORK = "/opt/pub-epreuve-nginx"
RACINE_POSTE = "/tmp/racine-epn.pem"
JOURNAL = "/var/log/nginx/epreuve.json"
RENOUVELER = "/usr/local/bin/renouveler-certificats"
SAUVEGARDER = "/usr/local/bin/sauvegarder-service"
RESTAURER = "/usr/local/bin/restaurer-service"
SONDE = "/usr/local/bin/sonde-alerte"
RECETTE = "/home/student/recette-initiale.md"
INCIDENT_YAML = "/home/student/incident.yaml"
DRAPEAU_INCIDENT = "/var/lib/pub-epn/incident-injecte"
COUCHES = ("amont", "tls", "droits", "entetes")
PORTS_ORIGINE = (18201, 18299)

# Pour chaque variante : les mots qui SUFFISENT à la reconnaître (`accepte`) et
# ceux qui la désignent SANS AMBIGUÏTÉ (`exclusifs`). Un composant qui porte un
# mot exclusif d'une AUTRE variante est refusé ; il doit porter au moins un mot
# accepté de la vraie. Tout est comparé après normalisation.
SIGNAUX = {
    "amont": {
        "exclusifs": ["18299", "pub-epn-api", "redeploiement", "drop-in", "dropin"],
        "accepte": [
            "18299", "pub-epn-api", "redeploiement", "drop-in", "dropin", "port",
            "upstream", "amont", "backend", "proxy_pass", "connection refused",
        ],
    },
    "tls": {
        "exclusifs": ["certificat", "certificate", "expire", "perime", "ssl_certificate"],
        "accepte": [
            "certificat", "certificate", "expire", "perime", "ssl_certificate",
            "cert", "tls", "ssl", "crt", "pem", "serie",
        ],
    },
    "droits": {
        "exclusifs": ["permission", "droits", "chmod", "chown", "0700", "eacces", "denied"],
        "accepte": [
            "permission", "droits", "chmod", "chown", "0700", "eacces", "denied",
            "mode", "acces", "proprietaire", "owner", "repertoire", "site",
        ],
    },
    "entetes": {
        "exclusifs": ["host", "en-tete", "entete", "header", "421", "proxy_set_header"],
        "accepte": [
            "host", "en-tete", "entete", "header", "421", "proxy_set_header",
            "misdirected", "nom public",
        ],
    },
}


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


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
def secret(edge):
    return yaml.safe_load(edge.run("sudo cat /root/.pub-epn-secret.yaml").stdout)


@pytest.fixture(scope="module")
def racine(poste, ip_edge):
    """L'autorité racine de Pebble, RÉCUPÉRÉE par le client et non supposée.

    Elle change à chaque démarrage de Pebble : l'écrire en dur rendrait le
    test faux au premier redémarrage du banc. Le `-k` ne sert ici qu'à joindre
    l'interface de gestion de Pebble, jamais à valider le service.

    Les racines SUCCESSIVES s'accumulent dans RACINE_POSTE. Le test de reprise
    redémarre edge.lab : Pebble tire alors une racine neuve, alors que le
    certificat servi a été signé, légitimement, par la précédente. Ne garder
    que la racine courante rendait la suite impossible à rejouer : 9/9 au
    premier passage, 8/9 au second (mesuré le 2026-10-31). Le paquet ne
    contient que des racines de l'autorité de test, et `racine=None` reste le
    cas qui doit échouer.
    """
    courante = f"{RACINE_POSTE}.courante"
    poste.run(
        f"curl -sk --max-time 10 https://{ip_edge}:15000/roots/0 -o {courante}"
    )
    presente = poste.run(f"grep -c 'BEGIN CERTIFICATE' {courante}")
    assert presente.stdout.strip() not in ("", "0"), message(
        en="The test authority root could not be fetched from the client "
        f"(https://{ip_edge}:15000/roots/0).",
        fr="La racine de l'autorité de test n'a pas pu être récupérée depuis "
        f"le client (https://{ip_edge}:15000/roots/0).",
    )
    # La 2e ligne d'un PEM est la première de ses données : propre à chaque
    # certificat, quand la ligne BEGIN est commune à toutes les racines.
    poste.run(
        f"touch {RACINE_POSTE}; "
        f'grep -qF "$(sed -n 2p {courante})" {RACINE_POSTE} '
        f"|| cat {courante} >> {RACINE_POSTE}"
    )
    return RACINE_POSTE


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------


def _norm(texte: str) -> str:
    """Minuscules, sans accents, ponctuation réduite à un espace.

    `_` est conservé : c'est le caractère de `proxy_pass` et de
    `proxy_set_header`, qu'un apprenant cite tels quels.
    """
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", str(texte).lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9_]+", " ", sans_accent).strip()


def _contient(composant_norm: str, signal: str) -> bool:
    return _norm(signal) in composant_norm


def _http(
    poste,
    ip: str,
    nom: str,
    chemin: str,
    *,
    racine: str | None,
    schema: str = "https",
    methode: str = "GET",
    entetes: tuple[str, ...] = (),
    utilisateur: str | None = None,
    brut: bool = False,
    delai: int = 15,
) -> tuple[str, str]:
    """Une requête depuis le client indépendant : (code, corps).

    `racine=None` n'ajoute AUCUNE autorité : c'est la requête qui doit échouer
    quand la validation est réellement stricte. Un code `000` signifie que
    curl n'a obtenu aucune réponse HTTP (refus, délai, certificat invalide).
    """
    port = 443 if schema == "https" else 80
    morceaux = [
        "curl", "-sS", "--max-time", str(delai),
        "-X", methode,
        "--resolve", f"{nom}:{port}:{ip}",
        "-o", "/dev/stdout", "-w", shlex.quote("\n%{http_code}"),
    ]
    if racine:
        morceaux += ["--cacert", racine]
    if brut:
        morceaux.append("--path-as-is")
    if utilisateur:
        morceaux += ["-u", shlex.quote(utilisateur)]
    for entete in entetes:
        morceaux += ["-H", shlex.quote(entete)]
    morceaux.append(shlex.quote(f"{schema}://{nom}{chemin}"))
    res = poste.run(" ".join(morceaux) + " 2>/dev/null")
    sortie = res.stdout.rsplit("\n", 1)
    corps = sortie[0] if len(sortie) == 2 else ""
    code = sortie[-1].strip() or "000"
    return code, corps


def _port_api(edge) -> int:
    res = edge.run("cat /run/pub-epn/api.port")
    return int(res.stdout.strip()) if res.stdout.strip().isdigit() else 18201


def _compteurs(edge) -> dict[str, int]:
    """Les fabrications de corps, lues à l'ORIGINE et jamais déduites d'un en-tête."""
    port = _port_api(edge)
    res = edge.run(
        f"curl -s --max-time 5 -H 'Host: {API}' http://127.0.0.1:{port}/_compteur"
    )
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"valeur": -1, "compte": -1}


def _serie(edge, nom: str) -> str:
    """Le numéro de série du certificat RÉELLEMENT servi pour ce nom."""
    res = edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
        "2>/dev/null | openssl x509 -noout -serial"
    )
    return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""


def _empreinte(edge, nom: str) -> str:
    res = edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
        "2>/dev/null | openssl x509 -noout -fingerprint -sha256"
    )
    return res.stdout.strip()


def _chemins_tls(edge) -> list[str]:
    """Les fichiers de clé et de certificat que la configuration CHARGÉE désigne."""
    res = edge.run(
        "sudo nginx -T 2>/dev/null | awk '$1==\"ssl_certificate\"||"
        "$1==\"ssl_certificate_key\"{gsub(/[;\"]/,\"\",$2); print $2}' | sort -u"
    )
    return [c for c in res.stdout.split() if c.startswith("/")]


def _attendre_retour(machine, limite_s: float = 180.0) -> bool:
    """Attend qu'une machine redémarrée réponde de nouveau.

    `testinfra` LÈVE quand la connexion SSH échoue, au lieu de rendre un
    résultat en échec. Une machine absente pendant son redémarrage n'est
    pourtant pas une erreur de test : c'est l'état qu'on attend.
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


def _msg(problemes: list[str]) -> str:
    return "\n".join(problemes)


# --------------------------------------------------------------------------
# Vérifications réutilisables : chacune rend la liste de ses problèmes
# --------------------------------------------------------------------------


def _verifier_publication(poste, ip, racine, secret) -> list[str]:
    """Le bon contenu par nom, sous TLS strict, et ce qui ne doit pas répondre."""
    p: list[str] = []
    tout = {"racine": racine}

    code, corps = _http(poste, ip, WWW, "/", **tout)
    if code != "200" or secret["repere_site"] not in corps:
        p.append(message(
            en=f"https://{WWW}/ answers {code} and does not carry the site "
            "content under strict validation.",
            fr=f"https://{WWW}/ répond {code} et ne porte pas le contenu du "
            "site sous validation stricte.",
        ))
    code, corps = _http(poste, ip, WWW, "/apropos.html", **tout)
    if code != "200" or secret["repere_apropos"] not in corps:
        p.append(message(
            en=f"https://{WWW}/apropos.html answers {code} without its content.",
            fr=f"https://{WWW}/apropos.html répond {code} sans son contenu.",
        ))

    nonce = secrets.token_hex(8)
    code, corps = _http(poste, ip, API, f"/v1/echo?nonce={nonce}", **tout)
    if code != "200" or nonce not in corps:
        p.append(message(
            en=f"https://{API}/v1/echo?nonce=... answers {code} and does not "
            "echo the nonce chosen for this run: the API is not really served.",
            fr=f"https://{API}/v1/echo?nonce=... répond {code} et ne renvoie "
            "pas le nonce choisi pour cet essai : l'API n'est pas réellement "
            "servie.",
        ))
    code, corps = _http(poste, ip, API, "/v1/valeur", **tout)
    if code != "200" or f'"valeur": {secret["valeur"]}' not in corps:
        p.append(message(
            en=f"https://{API}/v1/valeur answers {code} without the real "
            f"business value ({secret['valeur']}).",
            fr=f"https://{API}/v1/valeur répond {code} sans la vraie valeur "
            f"métier ({secret['valeur']}).",
        ))

    # Le routage par nom : chaque nom ne sert QUE ce qui lui revient.
    _, corps = _http(poste, ip, API, "/", **tout)
    if secret["repere_site"] in corps:
        p.append(message(
            en=f"{API} serves the static site: routing by name is wrong.",
            fr=f"{API} sert le site statique : le routage par nom est faux.",
        ))
    _, corps = _http(poste, ip, WWW, "/v1/valeur", **tout)
    if '"valeur"' in corps:
        p.append(message(
            en=f"{WWW} serves the API: routing by name is wrong.",
            fr=f"{WWW} sert l'API : le routage par nom est faux.",
        ))

    # Un nom inconnu (Host forgé sur une connexion TLS valide) ne tombe sur
    # aucun des deux contenus.
    _, corps = _http(
        poste, ip, WWW, "/", entetes=("Host: inconnu.epreuve.test",), **tout
    )
    if secret["repere_site"] in corps or '"valeur"' in corps:
        p.append(message(
            en="An unknown name falls on a real site: the default server "
            "serves content instead of refusing.",
            fr="Un nom inconnu tombe sur un vrai site : le serveur par défaut "
            "sert du contenu au lieu de refuser.",
        ))

    # La validation est réellement stricte : sans l'autorité de test, rien.
    code, _ = _http(poste, ip, WWW, "/", racine=None)
    if code == "200":
        p.append(message(
            en="The request succeeds without the test authority in the trust "
            "store: TLS validation is not strict.",
            fr="La requête aboutit sans l'autorité de test dans le magasin de "
            "confiance : la validation TLS n'est pas stricte.",
        ))

    # HTTP redirige vers HTTPS.
    for nom, chemin in ((WWW, "/"), (API, "/v1/valeur")):
        res = poste.run(
            f"curl -s -o /dev/null --max-time 10 --resolve {nom}:80:{ip} "
            f"-w '%{{http_code}} %{{redirect_url}}' http://{nom}{chemin}"
        )
        code, _, cible = res.stdout.strip().partition(" ")
        if code not in ("301", "308") or not cible.startswith(f"https://{nom}"):
            p.append(message(
                en=f"http://{nom}{chemin} answers {res.stdout.strip()!r}: it "
                "must redirect to the same name over HTTPS.",
                fr=f"http://{nom}{chemin} répond {res.stdout.strip()!r} : il "
                "doit rediriger vers le même nom en HTTPS.",
            ))
    return p


def _verifier_politique(poste, edge, ip, racine, secret) -> list[str]:
    """La matrice de refus et l'origine inaccessible."""
    p: list[str] = []
    tout = {"racine": racine}
    mdp = f"{secret['admin_utilisateur']}:{secret['admin_mot_de_passe']}"
    refus = ("401", "403")

    code, corps = _http(poste, ip, API, "/admin", **tout)
    if code not in refus or secret["secret_admin"] in corps:
        p.append(message(
            en=f"/admin without credentials answers {code}: it must be refused.",
            fr=f"/admin sans identifiants répond {code} : il doit être refusé.",
        ))
    code, corps = _http(poste, ip, API, "/admin", utilisateur="exploitation:faux", **tout)
    if code not in refus or secret["secret_admin"] in corps:
        p.append(message(
            en=f"/admin with a wrong password answers {code}.",
            fr=f"/admin avec un mauvais mot de passe répond {code}.",
        ))
    forges = (
        "X-Forwarded-For: 127.0.0.1",
        "X-Real-IP: 127.0.0.1",
        "X-Forwarded-User: exploitation",
        "X-Forwarded-Host: localhost",
    )
    code, corps = _http(poste, ip, API, "/admin", entetes=forges, **tout)
    if code not in refus or secret["secret_admin"] in corps:
        p.append(message(
            en=f"/admin with forged identity headers answers {code}: the "
            "decision must not rely on a header the client controls.",
            fr=f"/admin avec des en-têtes d'identité forgés répond {code} : la "
            "décision ne doit pas reposer sur un en-tête que le client "
            "contrôle.",
        ))
    for chemin in ("/admin/", "/admin/console"):
        code, corps = _http(poste, ip, API, chemin, **tout)
        if code not in refus or secret["secret_admin"] in corps:
            p.append(message(
                en=f"{chemin} without credentials answers {code}: the whole "
                "/admin subtree must be protected.",
                fr=f"{chemin} sans identifiants répond {code} : tout "
                "l'arbre /admin doit être protégé.",
            ))
    code, corps = _http(poste, ip, API, "/v1/../admin", brut=True, **tout)
    if secret["secret_admin"] in corps:
        p.append(message(
            en="/v1/../admin reaches the administration without credentials.",
            fr="/v1/../admin atteint l'administration sans identifiants.",
        ))
    code, corps = _http(poste, ip, API, "/admin", utilisateur=mdp, **tout)
    if code != "200" or secret["secret_admin"] not in corps:
        p.append(message(
            en=f"/admin with the right credentials answers {code}: legitimate "
            "access must keep working.",
            fr=f"/admin avec les bons identifiants répond {code} : l'accès "
            "légitime doit continuer de fonctionner.",
        ))
    _, corps = _http(poste, ip, WWW, "/admin", **tout)
    if secret["secret_admin"] in corps:
        p.append(message(
            en=f"{WWW}/admin reaches the administration.",
            fr=f"{WWW}/admin atteint l'administration.",
        ))
    _, corps = _http(poste, ip, API, "/admin", racine=None, schema="http")
    if secret["secret_admin"] in corps:
        p.append(message(
            en="/admin answers its content over plain HTTP.",
            fr="/admin répond son contenu en HTTP en clair.",
        ))

    # Les fichiers cachés du site restent cachés.
    for chemin in ("/.env", "/.git/HEAD"):
        code, corps = _http(poste, ip, WWW, chemin, **tout)
        if code not in ("403", "404") or secret["fuite_env"] in corps:
            p.append(message(
                en=f"{WWW}{chemin} answers {code}: hidden files must be "
                "refused and never leak.",
                fr=f"{WWW}{chemin} répond {code} : les fichiers cachés doivent "
                "être refusés et ne jamais fuiter.",
            ))

    # Les méthodes dont l'API n'a pas besoin sont refusées.
    for methode in ("PUT", "DELETE", "POST"):
        code, _ = _http(poste, ip, API, "/v1/valeur", methode=methode, **tout)
        if code not in ("403", "405"):
            p.append(message(
                en=f"{methode} /v1/valeur answers {code}: the proxy must refuse "
                "methods the service does not use (405).",
                fr=f"{methode} /v1/valeur répond {code} : le proxy doit refuser "
                "les méthodes dont le service n'a pas besoin (405).",
            ))

    # L'origine n'est joignable ni depuis le réseau, ni sur aucun de ses ports.
    ports = sorted({*PORTS_ORIGINE, _port_api(edge)})
    for port in ports:
        res = poste.run(
            f"curl -s -o /dev/null --max-time 4 -H 'Host: {API}' "
            f"-w '%{{http_code}}' http://{ip}:{port}/v1/valeur"
        )
        if res.stdout.strip() not in ("000", ""):
            p.append(message(
                en=f"The backend answers directly from the client on port "
                f"{port}: the origin must stay on the loopback interface.",
                fr=f"Le backend répond directement au client sur le port "
                f"{port} : l'origine doit rester sur l'interface de bouclage.",
            ))
    return p


def _verifier_cache_prive(poste, ip, racine, secret) -> list[str]:
    """Deux sessions alternées, cache chaud : aucune fuite, aucune erreur figée."""
    p: list[str] = []
    tout = {"racine": racine}

    code, _ = _http(poste, ip, API, "/v1/compte", **tout)
    if code != "401":
        p.append(message(
            en=f"/v1/compte without session answers {code}, not 401.",
            fr=f"/v1/compte sans session répond {code}, pas 401.",
        ))
    attendu = {"alpha": secret["marqueur_alpha"], "beta": secret["marqueur_beta"]}
    for tour in range(4):
        for session in ("alpha", "beta"):
            code, corps = _http(
                poste, ip, API, "/v1/compte",
                entetes=(f"Cookie: session={session}",), **tout,
            )
            if code != "200" or attendu[session] not in corps:
                p.append(message(
                    en=f"Round {tour + 1}: session {session} gets {code} and "
                    f"{corps.strip()[:100]!r}, not its own account. A private "
                    "response was stored and served to someone else.",
                    fr=f"Tour {tour + 1} : la session {session} reçoit {code} "
                    f"et {corps.strip()[:100]!r}, pas son propre compte. Une "
                    "réponse privée a été rangée puis servie à quelqu'un "
                    "d'autre.",
                ))
                return p
        code, _ = _http(poste, ip, API, "/v1/compte", **tout)
        if code != "401":
            p.append(message(
                en=f"Round {tour + 1}: an anonymous request gets {code}, not "
                "401: a cached account response is served without a session.",
                fr=f"Tour {tour + 1} : une requête anonyme reçoit {code}, pas "
                "401 : une réponse de compte rangée est servie sans session.",
            ))
            return p
    return p


def _mesurer_flux(poste, ip, racine) -> dict:
    """Les instants d'arrivée des six événements SSE, vus du client."""
    script = (
        "import json, socket, ssl, time\n"
        f"ctx = ssl.create_default_context(cafile={racine!r})\n"
        f"brut = socket.create_connection(({ip!r}, 443), timeout=20)\n"
        f"s = ctx.wrap_socket(brut, server_hostname={API!r})\n"
        "debut = time.monotonic()\n"
        f"s.sendall(b'GET /v1/flux HTTP/1.1\\r\\nHost: {API}\\r\\n"
        "Accept: text/event-stream\\r\\nConnection: close\\r\\n\\r\\n')\n"
        "vus = {}\n"
        "tampon = b''\n"
        "s.settimeout(20)\n"
        "try:\n"
        "    while len(vus) < 6:\n"
        "        morceau = s.recv(4096)\n"
        "        if not morceau:\n"
        "            break\n"
        "        tampon += morceau\n"
        "        for n in range(1, 7):\n"
        "            if n not in vus and ('evenement-%d' % n).encode() in tampon:\n"
        "                vus[n] = round(time.monotonic() - debut, 2)\n"
        "except OSError:\n"
        "    pass\n"
        "print(json.dumps({'statut_ok': tampon.startswith(b'HTTP/1.1 200'),"
        " 'vus': vus}))\n"
    )
    res = poste.run(f"python3 -c {shlex.quote(script)}")
    try:
        return json.loads(res.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"statut_ok": False, "vus": {}, "erreur": res.stderr[-200:]}


def _verifier_flux(poste, ip, racine) -> list[str]:
    mesure = _mesurer_flux(poste, ip, racine)
    vus = {int(k): v for k, v in mesure.get("vus", {}).items()}
    if len(vus) < 6:
        return [message(
            en=f"Only {len(vus)} of the 6 stream events arrived "
            f"({mesure.get('erreur', '')[:120]}): the long flow is cut or not "
            "published.",
            fr=f"Seuls {len(vus)} événements du flux sur 6 sont arrivés "
            f"({mesure.get('erreur', '')[:120]}) : le flux long est coupé ou "
            "pas publié.",
        )]
    if vus[1] >= 4:
        return [message(
            en=f"The first event took {vus[1]} s: the proxy buffers the "
            "stream and delivers it all at the end. Disable buffering on "
            "this route.",
            fr=f"Le premier événement a mis {vus[1]} s : le proxy met le flux "
            "en tampon et le livre d'un bloc à la fin. Désactivez la mise en "
            "tampon sur cette route.",
        )]
    if vus[6] - vus[1] < 3.5:
        return [message(
            en="The six events arrived together: the stream is not delivered "
            "at the backend's rhythm.",
            fr="Les six événements sont arrivés ensemble : le flux n'est pas "
            "livré au rythme du backend.",
        )]
    return []


def _verifier_etat_local(edge, ip) -> list[str]:
    """Le point d'état répond en local et jamais depuis l'adresse du réseau."""
    p: list[str] = []
    local = edge.run("curl -s --max-time 5 http://127.0.0.1:8081/nginx_status")
    if "Active connections" not in local.stdout:
        p.append(message(
            en="http://127.0.0.1:8081/nginx_status does not return the status "
            "page.",
            fr="http://127.0.0.1:8081/nginx_status ne rend pas la page d'état.",
        ))
    distant = edge.run(
        f"curl -s -o /dev/null --max-time 5 -w '%{{http_code}}' "
        f"http://{ip}:8081/nginx_status"
    )
    if distant.stdout.strip() == "200":
        p.append(message(
            en=f"The status page also answers on {ip}: anyone can read the "
            "live connection counts.",
            fr=f"La page d'état répond aussi sur {ip} : n'importe qui peut lire "
            "le nombre de connexions en cours.",
        ))
    return p


def _recette_complete(poste, edge, ip, racine, secret) -> list[str]:
    """La recette qu'un client indépendant rejoue, sans rien supposer."""
    return (
        _verifier_publication(poste, ip, racine, secret)
        + _verifier_politique(poste, edge, ip, racine, secret)
        + _verifier_cache_prive(poste, ip, racine, secret)
        + _verifier_flux(poste, ip, racine)
        + _verifier_etat_local(edge, ip)
    )


# --------------------------------------------------------------------------
# Point 1 : publication
# --------------------------------------------------------------------------


def test_publication_contenu_par_nom_et_tls_strict(poste, ip_edge, racine, secret) -> None:
    """CRITIQUE. Le bon contenu par nom, sous TLS strict, sans jamais `-k`.

    Le client est indépendant (poste.lab), le contenu est tiré au hasard à la
    pose du banc, et la requête sans l'autorité de test doit ÉCHOUER : c'est
    ce qui prouve que la validation est réellement stricte.
    """
    problemes = _verifier_publication(poste, ip_edge, racine, secret)
    assert not problemes, _msg(problemes)


def test_renouvellement_effectif_sans_redemarrage_ni_nouveau_compte(
    edge, poste, ip_edge, racine, secret
) -> None:
    """CRITIQUE. Une nouvelle série est servie, par reload, avec le même compte.

    La validation appelle le point d'entrée `renouveler-certificats` sans
    connaître le mécanisme choisi (minuterie, cron, crochet) : ce qu'elle
    mesure est la série RÉELLEMENT servie. Se réinscrire fonctionne, et ne doit
    pas être la réponse : face à une autorité réelle, cela consomme un quota.
    """
    assert edge.run(f"test -x {RENOUVELER}").rc == 0, message(
        en=f"{RENOUVELER} is missing or not executable. The validation needs "
        "an entry point to trigger a renewal without knowing the mechanism.",
        fr=f"{RENOUVELER} est absent ou non exécutable. La validation a besoin "
        "d'un point d'entrée pour déclencher un renouvellement sans connaître "
        "le mécanisme choisi.",
    )
    avant = {nom: _serie(edge, nom) for nom in NOMS}
    assert all(avant.values()), message(
        en="No certificate is served for one of the two names: nothing to "
        "renew.",
        fr="Aucun certificat n'est servi pour l'un des deux noms : il n'y a "
        "rien à renouveler.",
    )
    pid_avant = edge.run("systemctl show -p MainPID --value nginx").stdout.strip()
    commande_comptes = (
        f"sudo find {WORK}/lego/accounts -name '*.json' -printf '%p %s\\n' "
        "2>/dev/null | sort"
    )
    comptes_avant = edge.run(commande_comptes).stdout.strip()
    assert comptes_avant, message(
        en=f"No ACME account found under {WORK}/lego/accounts: the client "
        "must keep its account there.",
        fr=f"Aucun compte ACME sous {WORK}/lego/accounts : le client doit y "
        "conserver son compte.",
    )

    resultat = edge.run(f"sudo {RENOUVELER}")
    time.sleep(3)

    apres = {nom: _serie(edge, nom) for nom in NOMS}
    for nom in NOMS:
        assert apres[nom] and apres[nom] != avant[nom], message(
            en=f"The serial served for {nom} did not change ({avant[nom]!r} "
            f"then {apres[nom]!r}): the renewal did not happen or was not put "
            f"in service. {(resultat.stdout + resultat.stderr).strip()[-250:]}",
            fr=f"La série servie pour {nom} n'a pas changé ({avant[nom]!r} "
            f"puis {apres[nom]!r}) : le renouvellement n'a pas eu lieu ou "
            "n'a pas été mis en service. "
            f"{(resultat.stdout + resultat.stderr).strip()[-250:]}",
        )
    pid_apres = edge.run("systemctl show -p MainPID --value nginx").stdout.strip()
    assert pid_apres == pid_avant, message(
        en=f"Nginx was restarted ({pid_avant} then {pid_apres}): a renewal is "
        "put in service with a reload, which keeps live connections.",
        fr=f"Nginx a été redémarré ({pid_avant} puis {pid_apres}) : un "
        "renouvellement se met en service par un reload, qui conserve les "
        "connexions en cours.",
    )
    assert edge.run(commande_comptes).stdout.strip() == comptes_avant, message(
        en="The ACME account changed during the renewal: reuse the account on "
        "disk instead of registering again.",
        fr="Le compte ACME a changé pendant le renouvellement : réutilisez le "
        "compte présent sur le disque au lieu de vous réinscrire.",
    )

    # La nouvelle série se valide, et les clés restent fermées.
    for nom, chemin in ((WWW, "/"), (API, "/v1/echo?nonce=renouvele")):
        code, _ = _http(poste, ip_edge, nom, chemin, racine=racine)
        assert code == "200", message(
            en=f"After renewal, https://{nom}{chemin} no longer validates "
            f"strictly (HTTP {code}).",
            fr=f"Après le renouvellement, https://{nom}{chemin} ne se valide "
            f"plus strictement (HTTP {code}).",
        )
    chemins = [c for c in _chemins_tls(edge) if c.endswith(".key") or "key" in c]
    ouverts = edge.run(
        f"sudo find {WORK}/lego -type f \\( -name '*.key' -o -name '*.json' \\) "
        "-perm -o=r -printf '%M %p\\n'"
    ).stdout.strip()
    for chemin in chemins:
        mode = edge.run(f"sudo stat -c %a {shlex.quote(chemin)}").stdout.strip()
        if mode and int(mode[-1]) & 4:
            ouverts += f"\n{mode} {chemin}"
    assert not ouverts.strip(), message(
        en=f"These private keys or account files are readable by everyone:\n{ouverts}",
        fr=f"Ces clés privées ou fichiers de compte sont lisibles par tout le monde :\n{ouverts}",
    )


# --------------------------------------------------------------------------
# Point 2 : politique
# --------------------------------------------------------------------------


def test_politique_matrice_de_refus_et_origine_inaccessible(
    edge, poste, ip_edge, racine, secret
) -> None:
    """CRITIQUE. Accès interdits, en-têtes forgés, origine directe fermée.

    La protection que le banc pose lui-même (le backend n'écoute que sur la
    boucle locale) est fondue ici : seule, elle serait vraie avant tout
    travail. Ce test exige aussi les 401 de /admin, qui n'existent qu'avec la
    configuration de l'apprenant.
    """
    problemes = _verifier_politique(poste, edge, ip_edge, racine, secret)
    assert not problemes, _msg(problemes)


def test_politique_cache_utile_et_sans_fuite_entre_sessions(
    edge, poste, ip_edge, racine, secret
) -> None:
    """CRITIQUE. Le cache sert le public à l'origine près, jamais le privé.

    Deux mesures indissociables : un cache qui ne cache rien serait « sûr » et
    inutile ; un cache qui cache tout fuit. La preuve d'un HIT se lit dans le
    compteur de l'ORIGINE, jamais dans un en-tête que le proxy écrit lui-même.
    """
    jeton = secrets.token_hex(6)
    avant = _compteurs(edge)["valeur"]
    reponses = []
    for _ in range(3):
        code, corps = _http(poste, ip_edge, API, f"/v1/valeur?k={jeton}", racine=racine)
        reponses.append((code, corps))
    apres = _compteurs(edge)["valeur"]
    assert all(c == "200" and f'"valeur": {secret["valeur"]}' in b for c, b in reponses), message(
        en=f"The public route does not answer correctly: {reponses[0][0]}.",
        fr=f"La route publique ne répond pas correctement : {reponses[0][0]}.",
    )
    assert avant >= 0 and apres - avant <= 1, message(
        en=f"Three requests for the same public resource made the origin "
        f"produce {apres - avant} bodies. A working cache lets at most one "
        "through.",
        fr=f"Trois requêtes sur la même ressource publique ont fait produire "
        f"{apres - avant} corps à l'origine. Un cache qui fonctionne n'en "
        "laisse passer qu'un.",
    )
    problemes = _verifier_cache_prive(poste, ip_edge, racine, secret)
    assert not problemes, _msg(problemes)


# --------------------------------------------------------------------------
# Point 3 : operation
# --------------------------------------------------------------------------


def test_operation_flux_long_au_rythme_du_backend(poste, ip_edge, racine) -> None:
    """Le rythme, et non le nombre : la mise en tampon livre les six événements.

    Le premier événement doit arriver tout de suite et le dernier cinq
    secondes plus tard. Un test qui compterait les événements serait vert sur
    un proxy qui les retient tous.
    """
    problemes = _verifier_flux(poste, ip_edge, racine)
    assert not problemes, _msg(problemes)


def _lignes_depuis(edge, depuis: int) -> list[str]:
    res = edge.run(f"sudo tail -n +{depuis + 1} {JOURNAL}")
    return [ligne.strip() for ligne in res.stdout.splitlines() if ligne.strip()]


def _taille_journal(edge) -> int:
    res = edge.run(f"sudo wc -l {JOURNAL}")
    premier = res.stdout.strip().split(" ")[0] if res.stdout.strip() else "0"
    return int(premier) if premier.isdigit() else 0


def test_operation_journal_json_qui_mesure_et_etat_local(edge, poste, ip_edge, racine) -> None:
    """Un journal n'est pas une liste de champs : ses durées confrontées aux faits.

    `/v1/lent` dort deux secondes côté backend. Un `request_time` figé à zéro
    serait parsable et inutile ; l'erreur 404 de l'amont doit se lire comme
    telle. Le point d'état, lui, répond en local et nulle part ailleurs.
    """
    debut = _taille_journal(edge)
    _http(poste, ip_edge, API, "/v1/lent", racine=racine, delai=20)
    _http(poste, ip_edge, API, "/v1/introuvable", racine=racine)
    time.sleep(1)
    lignes = _lignes_depuis(edge, debut)
    assert lignes, message(
        en=f"{JOURNAL} received no line for the requests just made.",
        fr=f"{JOURNAL} n'a reçu aucune ligne pour les requêtes qui viennent "
        "d'être faites.",
    )
    objets = []
    for ligne in lignes:
        try:
            objets.append(json.loads(ligne))
        except json.JSONDecodeError:
            pytest.fail(message(
                en=f"A line of {JOURNAL} is not JSON: {ligne[:120]!r}. A "
                "collector drops every such line without a word.",
                fr=f"Une ligne de {JOURNAL} n'est pas du JSON : {ligne[:120]!r}. "
                "Un collecteur écarte chaque ligne de ce genre sans rien dire.",
            ))
    champs = ("status", "request_time", "upstream_response_time")
    for objet in objets:
        manquants = [c for c in champs if c not in objet]
        assert not manquants, message(
            en=f"A logged line lacks the fields {manquants}.",
            fr=f"Une ligne journalisée n'a pas les champs {manquants}.",
        )

    def _nombre(valeur) -> float:
        try:
            return float(str(valeur).split(",")[0].strip())
        except ValueError:
            return 0.0

    lent = [
        o for o in objets
        if str(o["status"]) == "200"
        and _nombre(o["request_time"]) >= 1.8
        and _nombre(o["upstream_response_time"]) >= 1.8
    ]
    assert lent, message(
        en="No logged line carries the 2 seconds the slow route really took, "
        "in both request_time and upstream_response_time: the durations do not "
        "measure.",
        fr="Aucune ligne journalisée ne porte les 2 secondes que la route "
        "lente a réellement prises, à la fois dans request_time et dans "
        "upstream_response_time : les durées ne mesurent rien.",
    )
    assert any(str(o["status"]) == "404" for o in objets), message(
        en="The 404 answered by the backend is not logged as a 404.",
        fr="Le 404 rendu par le backend n'est pas journalisé comme un 404.",
    )
    problemes = _verifier_etat_local(edge, ip_edge)
    assert not problemes, _msg(problemes)


def test_operation_alerte_se_declenche_sur_panne_puis_se_resout(
    edge, poste, ip_edge, racine
) -> None:
    """Une panne contrôlée du backend : l'alerte sonne, puis retombe.

    Le contrat de `sonde-alerte` est celui du scénario : code 0 quand le
    service est sain, code non nul quand il ne l'est pas. Ce que la sonde lit
    (une requête extérieure, le journal) lui appartient. La validation mesure
    les deux sens : une alerte qui ne sonne jamais ne protège rien, une alerte
    qui ne retombe jamais est ignorée.
    """
    assert edge.run(f"test -x {SONDE}").rc == 0, message(
        en=f"{SONDE} is missing or not executable.",
        fr=f"{SONDE} est absent ou non exécutable.",
    )
    sain = edge.run(f"sudo {SONDE}")
    assert sain.rc == 0, message(
        en=f"{SONDE} fails on a healthy service (exit {sain.rc}): "
        f"{(sain.stdout + sain.stderr).strip()[-200:]}",
        fr=f"{SONDE} échoue sur un service sain (code {sain.rc}) : "
        f"{(sain.stdout + sain.stderr).strip()[-200:]}",
    )

    try:
        edge.run("sudo systemctl stop pub-epn-api.service")
        codes = []
        for _ in range(4):
            code, _ = _http(
                poste, ip_edge, API, f"/v1/echo?nonce={secrets.token_hex(4)}",
                racine=racine,
            )
            codes.append(code)
        assert all(c.startswith("5") for c in codes), message(
            en=f"With the backend stopped, the API answers {codes}, not 5xx.",
            fr=f"Backend arrêté, l'API répond {codes}, pas des 5xx.",
        )
        sonnee = None
        for _ in range(3):
            sonnee = edge.run(f"sudo {SONDE}")
            if sonnee.rc != 0:
                break
            time.sleep(3)
        assert sonnee is not None and sonnee.rc != 0, message(
            en=f"{SONDE} still exits 0 while the API answers {codes}: the "
            "alert never fires.",
            fr=f"{SONDE} sort toujours à 0 alors que l'API répond {codes} : "
            "l'alerte ne sonne jamais.",
        )
        statuts = []
        for ligne in edge.run(f"sudo tail -n 40 {JOURNAL}").stdout.splitlines():
            try:
                statuts.append(str(json.loads(ligne).get("status", "")))
            except (json.JSONDecodeError, AttributeError):
                continue
        assert any(s.startswith("5") for s in statuts), message(
            en="The outage left no 5xx status in the access log.",
            fr="La panne n'a laissé aucun statut 5xx dans le journal d'accès.",
        )
    finally:
        edge.run("sudo systemctl start pub-epn-api.service")

    limite = time.monotonic() + 90
    retombee = None
    while time.monotonic() < limite:
        code, _ = _http(
            poste, ip_edge, API, f"/v1/echo?nonce={secrets.token_hex(4)}", racine=racine,
        )
        if code == "200":
            retombee = edge.run(f"sudo {SONDE}")
            if retombee.rc == 0:
                break
        time.sleep(4)
    assert retombee is not None and retombee.rc == 0, message(
        en="The backend is back and answering 200, yet the alert never "
        "resolves within 90 s: an alert that never falls back gets ignored.",
        fr="Le backend est revenu et répond 200, mais l'alerte ne se résout "
        "jamais en 90 s : une alerte qui ne retombe pas finit ignorée.",
    )


# --------------------------------------------------------------------------
# Point 4 : incident
# --------------------------------------------------------------------------


def test_incident_diagnostic_et_reparation_sans_perte_de_garantie(
    edge, poste, ip_edge, racine, secret
) -> None:
    """CRITIQUE. L'incident posé après la recette est nommé, puis corrigé.

    Quatre variantes, tirées au sort à la pose du banc et posées quand
    l'apprenant signale sa recette initiale. Le diagnostic structuré se compare
    au secret ; la réparation se juge par le comportement, et surtout par ce
    qu'elle n'a pas détruit : TLS strict, administration fermée, origine
    inaccessible, droits non élargis. Un compte rendu `explication` doit
    exister ; sa qualité est lue par un relecteur et n'est pas notée ici.
    """
    assert edge.run(f"test -s {RECETTE}").rc == 0, message(
        en=f"{RECETTE} does not exist or is empty. Writing your initial "
        "recette report is what triggers the incident.",
        fr=f"{RECETTE} n'existe pas ou est vide. L'écrire est ce qui déclenche "
        "l'incident.",
    )
    assert edge.run(f"test -e {DRAPEAU_INCIDENT}").rc == 0, message(
        en="The incident has not been injected yet. It follows the writing "
        f"of {RECETTE}.",
        fr=f"L'incident n'a pas encore été posé. Il suit l'écriture de {RECETTE}.",
    )

    res = edge.run(f"cat {INCIDENT_YAML}")
    assert res.rc == 0 and res.stdout.strip(), message(
        en=f"{INCIDENT_YAML} does not exist or is empty.",
        fr=f"{INCIDENT_YAML} n'existe pas ou est vide.",
    )
    diagnostic = yaml.safe_load(res.stdout) or {}
    couche = _norm(diagnostic.get("couche", ""))
    composant = _norm(diagnostic.get("composant", ""))
    explication = str(diagnostic.get("explication", "")).strip()
    vraie = secret["incident"]

    assert couche in COUCHES, message(
        en=f"The 'couche' field of {INCIDENT_YAML} must be one of "
        f"{list(COUCHES)}, got {couche!r}.",
        fr=f"Le champ 'couche' de {INCIDENT_YAML} doit valoir l'une de "
        f"{list(COUCHES)}, pas {couche!r}.",
    )
    assert couche == vraie, message(
        en=f"{INCIDENT_YAML} names layer {couche!r}, but the incident is on "
        "another layer.",
        fr=f"{INCIDENT_YAML} nomme la couche {couche!r}, mais l'incident est "
        "sur une autre couche.",
    )
    assert any(_contient(composant, s) for s in SIGNAUX[vraie]["accepte"]), message(
        en="The 'composant' field never names the faulty component. Name it "
        "there: the free-text 'explication' is not graded.",
        fr="Le champ 'composant' ne nomme jamais le composant fautif. Nommez-le "
        "dans ce champ : le texte libre 'explication' n'est pas noté.",
    )
    for autre, signaux in SIGNAUX.items():
        if autre == vraie:
            continue
        cites = [s for s in signaux["exclusifs"] if _contient(composant, s)]
        assert not cites, message(
            en=f"The 'composant' field also names another variant ({cites}): "
            "naming every layer at once is not a diagnosis. Ruled-out "
            "hypotheses belong in 'explication'.",
            fr=f"Le champ 'composant' nomme aussi une autre variante ({cites}) : "
            "tout citer à la fois n'est pas un diagnostic. Les hypothèses "
            "écartées ont leur place dans 'explication'.",
        )
    assert explication, message(
        en=f"{INCIDENT_YAML} carries no 'explication'. Its content is read by "
        "a human reviewer and not graded, but its absence is.",
        fr=f"{INCIDENT_YAML} ne porte aucune 'explication'. Son contenu est lu "
        "par un relecteur et n'est pas noté, mais son absence l'est.",
    )

    # La réparation passe par le proxy ou le système, jamais par le backend.
    sha = edge.run(f"sha256sum {WORK}/api.py").stdout.split()[0]
    assert sha == secret["api_sha256"], message(
        en="The backend source was modified. The backend is not yours to "
        "change: repair the publication around it.",
        fr="Le code du backend a été modifié. Le backend n'est pas à vous : "
        "réparez la publication autour de lui.",
    )
    if vraie == "entetes":
        assert edge.run("test -e /var/lib/pub-epn/exige-host").rc == 0, message(
            en="The backend's new requirement on the Host header was removed. "
            "Send the right Host from the proxy instead.",
            fr="L'exigence du backend sur l'en-tête Host a été retirée. "
            "Transmettez le bon Host depuis le proxy.",
        )

    # Le service répond de nouveau, plusieurs fois de suite, sous TLS strict.
    for essai in range(3):
        for nom, chemin in ((WWW, "/"), (API, "/v1/valeur"), (API, "/v1/echo?nonce=x")):
            code, _ = _http(poste, ip_edge, nom, chemin, racine=racine)
            assert code == "200", message(
                en=f"Attempt {essai + 1}/3: https://{nom}{chemin} answers {code} "
                "after the repair.",
                fr=f"Essai {essai + 1}/3 : https://{nom}{chemin} répond {code} "
                "après la réparation.",
            )

    # Aucune garantie perdue pour obtenir ce vert.
    problemes = _verifier_publication(poste, ip_edge, racine, secret)
    problemes += _verifier_politique(poste, edge, ip_edge, racine, secret)
    elargis = edge.run(f"sudo find {WORK}/site -perm -o+w").stdout.strip()
    if elargis:
        problemes.append(message(
            en=f"The repair opened write access to everyone:\n{elargis}",
            fr=f"La réparation a ouvert l'écriture à tout le monde :\n{elargis}",
        ))
    assert not problemes, _msg(problemes)


# --------------------------------------------------------------------------
# Point 5 : reprise (DERNIER : il coupe la machine)
# --------------------------------------------------------------------------


def test_reprise_restauration_puis_reboot_recette_complete(
    edge, poste, ip_edge, racine, secret
) -> None:
    """CRITIQUE. Sauvegarder, détruire, restaurer, redémarrer, rejouer la recette.

    La validation détruit la configuration (`/etc/nginx/conf.d`) et les
    fichiers de certificat et de clé que Nginx charge, redémarre Nginx à vide,
    puis appelle `restaurer-service`. Le certificat doit revenir IDENTIQUE
    (même empreinte) avec sa clé fermée. La machine est alors redémarrée : sans
    aucune intervention, la recette complète doit repasser.

    Pebble perd sa racine à chaque démarrage. Le certificat sur disque reste
    signé par l'ancienne : la validation garde donc l'ancienne racine et ne
    demande jamais un nouveau renouvellement après le redémarrage.
    """
    for script in (SAUVEGARDER, RESTAURER):
        assert edge.run(f"test -x {script}").rc == 0, message(
            en=f"{script} is missing or not executable.",
            fr=f"{script} est absent ou non exécutable.",
        )
    racine_pem = poste.run(f"cat {racine}").stdout
    racine_b64 = base64.b64encode(racine_pem.encode()).decode()

    empreintes = {nom: _empreinte(edge, nom) for nom in NOMS}
    assert all(empreintes.values()), message(
        en="No certificate is served before the backup.",
        fr="Aucun certificat n'est servi avant la sauvegarde.",
    )
    config_avant = edge.run("sudo nginx -T 2>/dev/null | sha256sum").stdout.split()[0]
    chemins = _chemins_tls(edge)
    assert chemins, message(
        en="The loaded configuration names no ssl_certificate.",
        fr="La configuration chargée ne désigne aucun ssl_certificate.",
    )

    sauvegarde = edge.run(f"sudo {SAUVEGARDER}")
    assert sauvegarde.rc == 0, message(
        en=f"{SAUVEGARDER} exits {sauvegarde.rc}: "
        f"{(sauvegarde.stdout + sauvegarde.stderr).strip()[-200:]}",
        fr=f"{SAUVEGARDER} sort avec {sauvegarde.rc} : "
        f"{(sauvegarde.stdout + sauvegarde.stderr).strip()[-200:]}",
    )

    # La perte : la configuration et les fichiers de certificat et de clé
    # chargés disparaissent, Nginx repart à vide.
    edge.run("sudo find /etc/nginx/conf.d -mindepth 1 -delete")
    for chemin in chemins:
        edge.run(f"sudo rm -f {shlex.quote(chemin)}")
    edge.run("sudo systemctl restart nginx")

    restauration = edge.run(f"sudo {RESTAURER}")
    assert restauration.rc == 0, message(
        en=f"{RESTAURER} exits {restauration.rc}: "
        f"{(restauration.stdout + restauration.stderr).strip()[-250:]}",
        fr=f"{RESTAURER} sort avec {restauration.rc} : "
        f"{(restauration.stdout + restauration.stderr).strip()[-250:]}",
    )
    time.sleep(2)

    assert edge.run("sudo nginx -t").rc == 0, message(
        en="After the restore, nginx -t fails.",
        fr="Après la restauration, nginx -t échoue.",
    )
    for nom in NOMS:
        assert _empreinte(edge, nom) == empreintes[nom], message(
            en=f"After the restore, the certificate served for {nom} is not "
            "the one saved (fingerprint differs): the backup must carry the "
            "certificates and their keys.",
            fr=f"Après la restauration, le certificat servi pour {nom} n'est "
            "pas celui qui a été sauvegardé (empreinte différente) : la "
            "sauvegarde doit porter les certificats et leurs clés.",
        )
    config_apres = edge.run("sudo nginx -T 2>/dev/null | sha256sum").stdout.split()[0]
    assert config_apres == config_avant, message(
        en="After the restore, the loaded configuration differs from the "
        "saved one.",
        fr="Après la restauration, la configuration chargée diffère de celle "
        "qui avait été sauvegardée.",
    )
    for chemin in chemins:
        if "key" in chemin:
            mode = edge.run(f"sudo stat -c %a {shlex.quote(chemin)}").stdout.strip()
            assert mode and not int(mode[-1]) & 4, message(
                en=f"After the restore, {chemin} is world-readable (mode {mode}): "
                "the backup must keep file modes.",
                fr=f"Après la restauration, {chemin} est lisible par tous (mode "
                f"{mode}) : la sauvegarde doit conserver les droits.",
            )
    problemes = _recette_complete(poste, edge, ip_edge, racine, secret)
    assert not problemes, _msg(problemes)

    # Le redémarrage de la machine, sans la moindre intervention ensuite.
    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)
    assert _attendre_retour(edge, 180), message(
        en="edge.lab did not come back within 180 s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180 s après le "
        "redémarrage.",
    )
    assert edge.run("systemctl is-enabled nginx").stdout.strip() == "enabled", message(
        en="Nginx is not enabled at boot (systemctl is-enabled nginx).",
        fr="Nginx n'est pas activé au démarrage (systemctl is-enabled nginx).",
    )

    # L'ancienne racine est reposée sur le client : elle seule signe le
    # certificat présent sur le disque.
    poste.run(f"echo {racine_b64} | base64 -d > {RACINE_POSTE}")
    limite = time.monotonic() + 150
    problemes = ["la recette n'a pas été tentée"]
    while time.monotonic() < limite:
        code, _ = _http(poste, ip_edge, WWW, "/", racine=RACINE_POSTE)
        if code == "200":
            problemes = _recette_complete(poste, edge, ip_edge, RACINE_POSTE, secret)
            break
        time.sleep(5)
    assert not problemes, message(
        en="After the reboot, the full recipe does not pass without "
        "intervention:\n",
        fr="Après le redémarrage, la recette complète ne repasse pas sans "
        "intervention :\n",
    ) + _msg(problemes)
