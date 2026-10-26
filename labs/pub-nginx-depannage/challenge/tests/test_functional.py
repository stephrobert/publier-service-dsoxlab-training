"""Verify the whole acceptance list after an unknown fault was repaired:
business routes, bounded waits, identities, backend reachability, and strict
TLS verification.

POURQUOI AUCUN TEST NE PARLE DE LA VARIANTE

La fixture tire une panne au hasard parmi cinq familles, et ne le dit a
personne. Ces tests ne peuvent donc pas verifier « la bonne correction » :
ils ne savent pas ce qui etait casse. Ils mesurent l'ETAT FINAL de la
recette, le meme pour les cinq variantes.

C'est une contrainte, et c'est aussi la bonne facon de faire : apres une
panne, un exploitant ne rejoue pas le test de ce qu'il vient de reparer, il
rejoue la recette entiere. C'est comme cela qu'on attrape la correction qui
a repare une chose en cassant une autre.

LES DEUX DESSERRAGES QUE LA RECETTE INTERDIT

Deux variantes se « reparent » en desserrant quelque chose, et les deux
marcheraient :

  `proxy_ssl_verify off` ferme la variante TLS en acceptant n'importe quel
  certificat de backend ;
  faire tourner les workers en root ferme la variante de permission sans
  toucher aux permissions.

La sonde de confiance /api-secondaire/ attrape la premiere, l'inspection
des processus la seconde. Les deux controles sont critiques.
"""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
ETAT = "/opt/pub-nginx-depannage/etat"
COMPOSANTS = (
    "nginx", "location", "permission", "droit", "dns", "resolution",
    "résolution", "hosts", "tls", "certificat", "autorite", "autorité",
    "timeout", "delai", "délai", "backend", "upstream", "proxy",
)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


@pytest.fixture(scope="module")
def marqueurs(edge):
    """Les trois marqueurs, lus sur la cible.

    Ils sont tires au hasard par la fixture : c'est ce qui rend une
    confusion de route mesurable. Deux backends qui rendraient le meme
    corps ne prouveraient rien.
    """
    lus = {}
    for quoi in ("app", "api", "statique"):
        lus[quoi] = edge.run(f"cat {ETAT}/nonce-{quoi}.txt").stdout.strip()
    manquants = [quoi for quoi, valeur in lus.items() if not valeur]
    assert not manquants, message(
        en=(
            f"The markers {manquants} could not be read under {ETAT}: the lab "
            "cannot be graded without them."
        ),
        fr=(
            f"Les marqueurs {manquants} n'ont pas pu être lus sous {ETAT} : le "
            "lab ne peut pas être évalué sans eux."
        ),
    )
    assert len(set(lus.values())) == 3, message(
        en=f"The three markers are not distinct ({lus}): a route mix-up "
           "would be invisible.",
        fr=f"Les trois marqueurs ne sont pas distincts ({lus}) : une confusion "
           "de route serait invisible.",
    )
    return lus


def _demander(poste, cible: str, chemin: str, delai: int = 20) -> tuple[str, str]:
    """Le code de statut et le corps, depuis le client independant."""
    sortie = poste.run(
        f"curl -s --max-time {delai} -w '\\n%{{http_code}}' "
        f"-H 'Host: publication.lab.test' http://{cible}{chemin}"
    ).stdout
    if "\n" not in sortie:
        return "000", sortie
    corps, code = sortie.rsplit("\n", 1)
    return code.strip(), corps


def test_le_dossier_de_diagnostic_existe_et_nomme_un_composant(edge) -> None:
    """Le dossier de diagnostic, et ce que la machine en juge.

    Elle juge sa PRESENCE et le fait qu'il nomme un composant. Elle ne
    juge pas le raisonnement, et ne le pretend pas : c'est un relecteur
    qui le lit. Un controle automatique qui noterait la qualite d'une
    explication noterait en realite la presence de mots-cles, et
    apprendrait a en semer.
    """
    chemin = "/opt/pub-nginx-depannage/diagnostic.md"
    assert edge.file(chemin).exists, message(
        en=(
            f"{chemin} is missing. The acceptance list asks for the component "
            "in cause, the cause, and the observations that led there."
        ),
        fr=(
            f"{chemin} est absent. La recette demande le composant en cause, "
            "la cause, et les observations qui y ont mené."
        ),
    )
    texte = edge.file(chemin).content_string
    assert len(texte.strip()) >= 120, message(
        en=(
            f"The diagnosis file holds {len(texte.strip())} characters. Three "
            "things are expected: the component, the cause, and what you "
            "observed."
        ),
        fr=(
            f"Le dossier de diagnostic contient {len(texte.strip())} "
            "caractères. Trois choses sont attendues : le composant, la cause, "
            "et ce que vous avez observé."
        ),
    )
    minuscule = texte.lower()
    assert any(mot in minuscule for mot in COMPOSANTS), message(
        en=(
            "The diagnosis file does not name any component of the stack. A "
            "reviewer reads the reasoning; the automated check only verifies "
            "that a component is named at all."
        ),
        fr=(
            "Le dossier de diagnostic ne nomme aucun composant de la pile. Un "
            "relecteur lit le raisonnement ; le contrôle automatique vérifie "
            "seulement qu'un composant est nommé."
        ),
    )


def test_la_recette_metier_passe_en_entier(poste, ip_edge, marqueurs) -> None:
    """Les routes, les marqueurs, et la borne d'attente.

    Chaque route doit rendre SON marqueur. C'est ce qui attrape la
    correction qui retablit une route en la faisant pointer vers le
    backend voisin, lequel repond 200 sans broncher.
    """
    code, corps = _demander(poste, ip_edge, "/")
    assert code == "200" and marqueurs["statique"] in corps, message(
        en=(
            f"The static root answered {code} / {corps!r} and does not carry "
            f"its marker {marqueurs['statique']}. It is served by Nginx from "
            "/var/www/catalogue, not by a backend."
        ),
        fr=(
            f"La racine statique a répondu {code} / {corps!r} et ne porte pas "
            f"son marqueur {marqueurs['statique']}. Elle est servie par Nginx "
            "depuis /var/www/catalogue, et non par un backend."
        ),
    )

    for route, attendu, voisin in (
        ("/app/", "app", "api"),
        ("/api/", "api", "app"),
    ):
        code, corps = _demander(poste, ip_edge, route)
        assert code == "200", message(
            en=f"{route} answered {code} / {corps!r} instead of 200.",
            fr=f"{route} a répondu {code} / {corps!r} au lieu de 200.",
        )
        assert marqueurs[voisin] not in corps, message(
            en=(
                f"{route} returned the {voisin} backend's marker: the route "
                "reaches the wrong backend, which answers 200 without "
                "complaining. A status code alone would have reported green."
            ),
            fr=(
                f"{route} a rendu le marqueur du backend {voisin} : la route "
                "atteint le mauvais backend, qui répond 200 sans broncher. Un "
                "code de statut seul aurait conclu au vert."
            ),
        )
        assert marqueurs[attendu] in corps, message(
            en=(
                f"{route} answered 200 but does not carry the {attendu} "
                f"backend's marker: {corps!r}."
            ),
            fr=(
                f"{route} a répondu 200 mais ne porte pas le marqueur du "
                f"backend {attendu} : {corps!r}."
            ),
        )

    code, corps = _demander(poste, ip_edge, "/api/lent")
    assert code == "200", message(
        en=(
            f"/api/lent answered {code} / {corps!r}. It takes about three "
            "seconds, which the acceptance list allows: a bound that refuses "
            "legitimate slowness is an outage you inflict on yourself."
        ),
        fr=(
            f"/api/lent a répondu {code} / {corps!r}. Elle prend environ trois "
            "secondes, ce que la recette autorise : une borne qui refuse une "
            "lenteur légitime est une panne qu'on s'infligeait."
        ),
    )

    code, _ = _demander(poste, ip_edge, "/api/sans-fin", delai=20)
    assert code == "504", message(
        en=(
            f"A request that never advances answered {code} after 20 seconds, "
            "not 504. The acceptance list asks for it to be cut in under "
            "fifteen seconds. Note what 000 means here: curl gave up, not the "
            "proxy. An absent bound is not a wide bound, it is no bound: the "
            "connection stays open until the client walks away, and the worker "
            "with it."
        ),
        fr=(
            f"Une requête qui n'avance plus a répondu {code} après vingt "
            "secondes, et non 504. La recette demande qu'elle soit coupée en "
            "moins de quinze secondes. Lisez bien ce que 000 veut dire ici : "
            "c'est curl qui a abandonné, pas le proxy. Une borne absente n'est "
            "pas une borne large, c'est une absence de borne : la connexion "
            "reste ouverte jusqu'à ce que le client renonce, et le worker avec "
            "elle."
        ),
    )


def test_la_correction_n_a_pas_donne_de_droits_excessifs(
    poste, edge, ip_edge
) -> None:
    """CRITIQUE. Reparer en elargissant les droits est la facilite.

    La variante de permission se « corrige » en faisant tourner les workers
    en root, et la racine statique se « corrige » en 0777. Les deux
    marchent. Les deux sont des regressions, et elles survivent au
    redemarrage.
    """
    processus = edge.run("ps -o user=,args= -C nginx").stdout
    workers = [
        ligne for ligne in processus.splitlines() if "worker process" in ligne
    ]
    assert workers, message(
        en=(
            f"No Nginx worker process is running (ps said {processus!r}): the "
            "service is not up."
        ),
        fr=(
            f"Aucun worker Nginx ne tourne (ps a rendu {processus!r}) : le "
            "service n'est pas debout."
        ),
    )
    en_root = [ligne for ligne in workers if ligne.split()[0] == "root"]
    assert not en_root, message(
        en=(
            f"{len(en_root)} Nginx worker(s) run as root. The master binds "
            "port 80 as root and that is normal; the workers, which handle "
            "untrusted traffic, must drop to an unprivileged user. Running "
            "them as root makes any permission problem disappear, which is "
            "precisely why it is tempting."
        ),
        fr=(
            f"{len(en_root)} worker(s) Nginx tournent sous root. Le master "
            "ouvre le port 80 en root, et c'est normal ; les workers, qui "
            "traitent du trafic non fiable, doivent redescendre sur un compte "
            "sans privilège. Les faire tourner en root fait disparaître tout "
            "problème de permission, et c'est précisément pour cela que c'est "
            "tentant."
        ),
    )

    for port in (18101, 18102, 18103):
        code = poste.run(
            f"curl -s -o /dev/null --max-time 5 -w '%{{http_code}}' "
            f"http://{ip_edge}:{port}/"
        ).stdout.strip()
        assert code == "000", message(
            en=(
                f"Backend port {port} answered {code} from the independent "
                "client: it is reachable from the network. The backends listen "
                "on the loopback, and nothing in the acceptance list asks for "
                "that to change. A backend published directly is a route "
                "around every control the proxy carries."
            ),
            fr=(
                f"Le port backend {port} a répondu {code} depuis le client "
                "indépendant : il est joignable depuis le réseau. Les backends "
                "écoutent sur la boucle locale, et rien dans la recette ne "
                "demande d'en changer. Un backend publié directement est un "
                "contournement de tous les contrôles que porte le proxy."
            ),
        )

    mode = edge.run("stat -c '%a' /var/www/catalogue").stdout.strip()
    assert mode, message(
        en="/var/www/catalogue does not exist: the static root is gone.",
        fr="/var/www/catalogue n'existe pas : la racine statique a disparu.",
    )
    assert int(mode[-1]) & 0o2 == 0, message(
        en=(
            f"/var/www/catalogue is mode {mode}: it is world-writable. Making "
            "a directory 0777 does make a 403 go away, and it lets anyone who "
            "reaches the machine replace the pages being served."
        ),
        fr=(
            f"/var/www/catalogue est en {mode} : ouvert en écriture à tout le "
            "monde. Passer un répertoire en 0777 fait bien disparaître un 403, "
            "et laisse quiconque atteint la machine remplacer les pages "
            "servies."
        ),
    )


def test_la_verification_tls_est_restee_stricte(
    poste, ip_edge, marqueurs
) -> None:
    """CRITIQUE. La sonde de confiance, et son contre-exemple.

    /api-secondaire/ pointe vers un backend dont le certificat vient d'une
    autre autorite et dont le SAN ne correspond pas. Elle doit repondre
    502. Et /api/ doit repondre 200 : une verification stricte qui refuse
    aussi le bon backend n'a rien verifie, elle a tout ferme.
    """
    code, corps = _demander(poste, ip_edge, "/api-secondaire/")
    assert marqueurs["api"] not in corps, message(
        en=(
            "The trust probe returned the api marker: Nginx accepted a backend "
            "whose certificate comes from another authority, with a "
            "non-matching SAN. TLS verification has been loosened, probably "
            "with `proxy_ssl_verify off`, and the real backend's answer is now "
            "indistinguishable from an impostor's."
        ),
        fr=(
            "La sonde de confiance a rendu le marqueur de l'api : Nginx a "
            "accepté un backend dont le certificat vient d'une autre autorité, "
            "avec un SAN qui ne correspond pas. La vérification TLS a été "
            "desserrée, probablement par `proxy_ssl_verify off`, et la réponse "
            "du vrai backend est désormais indiscernable de celle d'un "
            "imposteur."
        ),
    )
    assert code == "502", message(
        en=(
            f"The trust probe answered {code}, not 502. It exists for one "
            "purpose: to stay refused. Its backend is not trustworthy, and its "
            "refusal is the proof that the proxy verifies what it connects to."
        ),
        fr=(
            f"La sonde de confiance a répondu {code}, et non 502. Elle n'existe "
            "que pour une chose : rester refusée. Son backend n'est pas digne "
            "de confiance, et son refus est la preuve que le proxy vérifie ce "
            "à quoi il se connecte."
        ),
    )

    code, corps = _demander(poste, ip_edge, "/api/")
    assert code == "200" and marqueurs["api"] in corps, message(
        en=(
            f"The trust probe is refused, but /api/ answered {code} / {corps!r} "
            "too. Verification that refuses the legitimate backend as well has "
            "not verified anything: it has closed everything. The lab's own "
            "authority is on disk, and the backend's certificate was issued by "
            "it."
        ),
        fr=(
            f"La sonde de confiance est bien refusée, mais /api/ a répondu "
            f"{code} / {corps!r} aussi. Une vérification qui refuse également "
            "le backend légitime n'a rien vérifié : elle a tout fermé. "
            "L'autorité du lab est sur le disque, et le certificat du backend "
            "en est issu."
        ),
    )
