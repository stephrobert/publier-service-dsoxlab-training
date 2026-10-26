"""Verify served resources and their MIME types, a fallback that does not turn
errors into successes, refusal of private files, and worker-readable but not
world-readable permissions.

LE CONTROLE QUI SURPREND, ET IL EST LE DEUXIEME

Un `try_files ... /index.html` pose sur la racine transforme TOUTE erreur en
succes : une ressource absente rend 200 avec du HTML, et un appel d'API
inconnu aussi. Le navigateur affiche alors l'application a la place de la
reponse attendue, et le defaut se diagnostique des semaines plus tard, quand
quelqu'un remarque qu'un `fetch` recoit du HTML.

Le fallback reste pourtant LEGITIME pour les routes de l'application : le
test exige donc les deux, et c'est ce qui distingue une publication correcte
d'une publication qui marche.
"""

from __future__ import annotations

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
NOM = "app.lab.test"
RACINE_WEB = "/opt/pub-nginx-statique/site"

SECRETS = ("secret-ne-doit-jamais-sortir-4f21", "secret-prive-8a33")


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _reponse(poste, ip: str, chemin: str) -> tuple[str, str, str]:
    """Rend (statut, type MIME, corps) en UNE requete.

    Trois appels separes mesureraient trois requetes, donc potentiellement
    trois etats : ici le statut et le type viennent des en-tetes de la meme
    reponse que le corps.
    """
    sortie = poste.run(
        f"curl -s --max-time 10 -H 'Host: {NOM}' "
        f"-w '@@%{{http_code}}@@%{{content_type}}' http://{ip}{chemin}"
    ).stdout
    morceaux = sortie.split("@@")
    corps = morceaux[0] if morceaux else ""
    statut = morceaux[1] if len(morceaux) > 1 else "000"
    mime = morceaux[2] if len(morceaux) > 2 else ""
    return statut, mime, corps


def test_les_ressources_prevues_ont_corps_et_type_correct(poste, ip_edge) -> None:
    """Le contenu sort, et avec le type qui permet au navigateur de s'en servir.

    Un JavaScript servi en `application/octet-stream` est telecharge au lieu
    d'etre execute : la page se charge, et l'application ne demarre pas.
    """
    cas = [
        ("/", "text/html", "<div id=\"app\">"),
        ("/assets/app.js", "javascript", "application monopage"),
        ("/assets/app.css", "text/css", "font-family"),
    ]
    ecarts = []
    for chemin, type_attendu, marque in cas:
        statut, mime, corps = _reponse(poste, ip_edge, chemin)
        if statut != "200":
            ecarts.append(f"{chemin} : HTTP {statut}")
        elif marque not in corps:
            ecarts.append(f"{chemin} : le contenu attendu n'y est pas")
        elif type_attendu not in mime:
            ecarts.append(f"{chemin} : type {mime!r} au lieu de {type_attendu!r}")
    assert not ecarts, message(
        en=(
            "Served resources must carry the right body and MIME type: "
            + " ; ".join(ecarts)
            + ". A JavaScript served as application/octet-stream is downloaded "
            "instead of executed, and the application never starts."
        ),
        fr=(
            "Les ressources servies doivent porter le bon corps et le bon type "
            "MIME : " + " ; ".join(ecarts)
            + ". Un JavaScript servi en application/octet-stream est téléchargé "
            "au lieu d'être exécuté, et l'application ne démarre jamais."
        ),
    )


def test_le_fallback_ne_transforme_pas_une_erreur_en_succes(poste, ip_edge) -> None:
    """Les deux moities : le fallback marche pour l'application, et SEULEMENT.

    C'est le defaut le plus couteux du lab, parce qu'il ne se voit pas : la
    page s'affiche, et c'est un `fetch` qui recevra du HTML dans trois
    semaines.
    """
    statut, _, corps = _reponse(poste, ip_edge, "/accueil")
    assert statut == "200" and "<div id=" in corps, message(
        en=(
            f"/accueil must fall back to the application (HTTP {statut}). A "
            "single-page application needs its routes served by index.html."
        ),
        fr=(
            f"/accueil doit retomber sur l'application (HTTP {statut}). Une "
            "application monopage a besoin que ses routes soient servies par "
            "index.html."
        ),
    )

    ecarts = []
    statut, _, corps = _reponse(poste, ip_edge, "/assets/absent.js")
    if statut != "404":
        ecarts.append(f"/assets/absent.js : HTTP {statut} au lieu de 404")

    statut, mime, corps = _reponse(poste, ip_edge, "/api/inconnu")
    if statut != "404" or "json" not in mime:
        ecarts.append(
            f"/api/inconnu : HTTP {statut}, type {mime!r} au lieu d'un 404 JSON"
        )

    statut, mime, corps = _reponse(poste, ip_edge, "/api/existe")
    if statut != "200" or "json" not in mime:
        ecarts.append(f"/api/existe : HTTP {statut}, type {mime!r}")

    assert not ecarts, message(
        en=(
            "The fallback is swallowing real errors: " + " ; ".join(ecarts)
            + ". Scope it to the application's own routes, and let missing "
            "assets and the API answer for themselves."
        ),
        fr=(
            "Le fallback avale de vraies erreurs : " + " ; ".join(ecarts)
            + ". Limitez-le aux routes de l'application, et laissez les "
            "ressources absentes et l'API répondre pour elles-mêmes."
        ),
    )


def test_les_fichiers_prives_et_les_traversees_sont_refuses(poste, ip_edge) -> None:
    """CRITIQUE. On cherche le SECRET dans le corps, pas seulement un statut.

    Un 200 qui rend index.html sur `/.env` n'est pas une fuite ; un 200 qui
    rend la cle en est une. Le statut seul ne les distingue pas, et c'est
    exactement le piege que le fallback tend ici.
    """
    fuites = []
    for chemin in ("/.env", "/deploiement.interne", "/../../etc/passwd",
                   "/..%2f..%2fetc%2fpasswd"):
        statut, _, corps = _reponse(poste, ip_edge, chemin)
        for secret in SECRETS:
            if secret in corps:
                fuites.append(f"{chemin} a rendu un secret (HTTP {statut})")
        if "root:x:" in corps:
            fuites.append(f"{chemin} a rendu /etc/passwd (HTTP {statut})")
    assert not fuites, message(
        en=(
            "Private content left the server: " + " ; ".join(fuites)
            + ". Refuse dotfiles and the private file explicitly; a status code "
            "alone does not tell a refusal from a fallback that happens to "
            "return HTML."
        ),
        fr=(
            "Du contenu privé est sorti : " + " ; ".join(fuites)
            + ". Refusez explicitement les dotfiles et le fichier privé ; un "
            "code de statut seul ne distingue pas un refus d'un fallback qui "
            "rend du HTML."
        ),
    )


def test_les_droits_permettent_aux_workers_de_lire_sans_ouvrir_a_tous(
    edge, poste, ip_edge
) -> None:
    """CRITIQUE, et les deux moities comptent, encore.

    Retirer tous les droits protege parfaitement et ne sert plus rien. On
    exige donc que les ressources soient TOUJOURS servies, et que plus
    personne d'autre que le proprietaire et le groupe ne puisse les lire sur
    le disque.
    """
    ouverts = edge.run(
        f"sudo find {RACINE_WEB} -type f -perm -o=r -printf '%M %p\\n'"
    ).stdout.strip()
    assert not ouverts, message(
        en=(
            "These files are readable by everyone on the machine:\n"
            f"{ouverts}\n"
            "Nginx workers run as www-data: give them read access through "
            "ownership or group, not by opening the files to all."
        ),
        fr=(
            "Ces fichiers sont lisibles par tout le monde sur la machine :\n"
            f"{ouverts}\n"
            "Les workers de Nginx tournent sous www-data : donnez-leur la "
            "lecture par la propriété ou le groupe, pas en ouvrant les fichiers "
            "à tous."
        ),
    )

    statut, _, corps = _reponse(poste, ip_edge, "/assets/app.js")
    assert statut == "200" and "application monopage" in corps, message(
        en=(
            f"The asset is no longer served (HTTP {statut}). Closing the "
            "permissions must not take the workers' read access with it: that "
            "is an outage, not a hardening."
        ),
        fr=(
            f"La ressource n'est plus servie (HTTP {statut}). Fermer les droits "
            "ne doit pas emporter la lecture des workers : c'est une panne, pas "
            "un durcissement."
        ),
    )
