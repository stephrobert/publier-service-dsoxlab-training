"""Verify the weights, the removal of an unready backend inside the window,
the absence of a switchover on a dip shorter than the threshold, and that
draining stops new assignments without cutting an established flow.

CE QUE LE SETUP POSE : deux backends pilotables par un fichier d'état, et un
HAProxy qui tourne SANS aucune sonde, à poids égaux.

CE QUI MESURE, ET POURQUOI CE N'EST PAS UN ETAT

Les contrôles 2 et 3 ne lisent pas l'état d'un serveur, ils lisent les
COMPTEURS DE TRANSITION de HAProxy (`chkfail`, `chkdown`).

La raison est qu'un état ne distingue pas deux histoires opposées. Un serveur
`UP` dix secondes après une panne courte peut n'avoir jamais été retiré, ou
avoir été retiré puis remis : avec `rise 3` et `inter 1`, les deux donnent
`UP` au même instant. Seul `chkdown` dit laquelle des deux a eu lieu, et c'est
exactement la différence entre une sonde stable et une sonde qui oscille.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
RECETTE = "/opt/pub-haproxy-sante/recette.txt"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _lignes(edge, cle: str) -> list[str]:
    sortie = edge.run(f"grep -oP '(?<=^{cle} = ).*' {RECETTE}").stdout
    return [ligne.strip() for ligne in sortie.splitlines() if ligne.strip()]


def _valeur(edge, cle: str) -> str:
    lues = _lignes(edge, cle)
    assert len(lues) == 1, message(
        en=f"The recipe {RECETTE} declares {len(lues)} `{cle}`, expected one.",
        fr=f"La recette {RECETTE} déclare {len(lues)} `{cle}`, on en attend un.",
    )
    return lues[0]


@pytest.fixture(scope="module")
def recette(edge) -> dict:
    """Tout ce que la recette prescrit, lu une fois."""
    poids = {}
    for ligne in _lignes(edge, "poids"):
        nom, valeur = ligne.split()
        poids[nom] = int(valeur)
    etats = {}
    for ligne in _lignes(edge, "etat"):
        nom, chemin = ligne.split()
        etats[nom] = chemin
    return {
        "poids": poids,
        "etats": etats,
        "inter": int(_valeur(edge, "inter")),
        "fall": int(_valeur(edge, "fall")),
        "rise": int(_valeur(edge, "rise")),
        "sonde": _valeur(edge, "sonde"),
        "backend": _valeur(edge, "backend"),
        "socket": _valeur(edge, "socket_admin"),
    }


def _piloter(edge, recette, commande: str) -> str:
    return edge.run(
        f"echo '{commande}' | sudo socat -t3 stdio {recette['socket']}"
    ).stdout


def _table(edge, recette) -> dict[str, dict[str, str]]:
    """La ligne de `show stat` de chaque serveur du backend, par nom.

    L'en-tete est lu pour trouver les colonnes : les positionner en dur
    marcherait aujourd'hui et se decalerait a la premiere colonne ajoutee par
    une version de HAProxy.
    """
    brut = _piloter(edge, recette, "show stat")
    lignes = [ligne for ligne in brut.splitlines() if ligne.strip()]
    assert lignes and lignes[0].startswith("#"), message(
        en=(
            "`show stat` returned nothing usable through the runtime socket "
            f"(answer: {brut.strip()[:160]!r})."
        ),
        fr=(
            "`show stat` n'a rien rendu d'exploitable par le socket "
            f"d'administration (réponse : {brut.strip()[:160]!r})."
        ),
    )
    colonnes = lignes[0].lstrip("# ").rstrip(",").split(",")
    serveurs: dict[str, dict[str, str]] = {}
    for ligne in lignes[1:]:
        champs = ligne.split(",")
        if len(champs) < len(colonnes):
            continue
        enregistrement = dict(zip(colonnes, champs, strict=False))
        if enregistrement.get("pxname") != recette["backend"]:
            continue
        nom = enregistrement.get("svname", "")
        if nom in ("FRONTEND", "BACKEND"):
            continue
        serveurs[nom] = enregistrement
    return serveurs


def _entier(enregistrement: dict[str, str], colonne: str) -> int:
    valeur = enregistrement.get(colonne, "")
    return int(valeur) if valeur.isdigit() else 0


def _statut(enregistrement: dict[str, str]) -> str:
    """L'etat d'un serveur, SANS son compteur de transition.

    `show stat` ne rend pas « UP » mais « UP 4/5 » pendant qu'une sonde
    remonte, et « DOWN 1/3 » pendant qu'elle descend : le suffixe est le
    nombre de controles deja obtenus sur ceux qu'il faut. Mesure du
    2026-10-26 : comparer la colonne entiere a « UP » fait lire une montee
    en cours comme un retrait, puisque « UP 4/5 » n'est pas « UP ». Le test
    concluait alors qu'un serveur etait sorti alors qu'il rentrait, et
    s'etonnait ensuite que `chkdown` n'ait pas bouge.

    On ne garde donc que l'etat, qui est le premier mot.
    """
    return enregistrement.get("status", "").split()[0] if enregistrement.get("status") else ""


def _etat_backend(edge, recette, nom: str, valeur: str) -> None:
    chemin = recette["etats"][nom]
    edge.run(f"echo {valeur} | sudo tee {chemin} >/dev/null")


def _echantillon(poste, ip: str, nombre: int) -> dict[str, int]:
    sortie = poste.run(f"echantillon {ip} {nombre}").stdout
    comptes: dict[str, int] = {}
    for ligne in sortie.splitlines():
        if not ligne.strip():
            continue
        cle, compte = ligne.rsplit(" ", 1)
        comptes[cle] = int(compte)
    return comptes


def _attendre(condition, limite_s: float, pas: float = 0.5):
    """Attend qu'une condition soit vraie, et rend ce qu'elle a vu en dernier."""
    limite = time.monotonic() + limite_s
    dernier = None
    while time.monotonic() < limite:
        dernier = condition()
        if dernier:
            return dernier
        time.sleep(pas)
    return dernier


def test_la_sonde_est_de_niveau_sept_et_les_poids_sont_ceux_de_la_recette(
    edge, poste, ip_edge, recette
) -> None:
    """Les poids décident de la part, et la sonde lit une réponse applicative."""
    serveurs = _table(edge, recette)
    assert set(serveurs) >= set(recette["poids"]), message(
        en=(
            f"Backend {recette['backend']} does not carry the servers "
            f"{sorted(recette['poids'])} (seen: {sorted(serveurs)})."
        ),
        fr=(
            f"Le backend {recette['backend']} ne porte pas les serveurs "
            f"{sorted(recette['poids'])} (vus : {sorted(serveurs)})."
        ),
    )

    for nom, poids in recette["poids"].items():
        enregistrement = serveurs[nom]
        assert _statut(enregistrement) == "UP", message(
            en=(
                f"Server {nom} is {enregistrement.get('status')!r}, expected UP "
                "before anything is measured."
            ),
            fr=(
                f"Le serveur {nom} est {enregistrement.get('status')!r}, on "
                "attend UP avant toute mesure."
            ),
        )
        assert _entier(enregistrement, "weight") == poids, message(
            en=(
                f"Server {nom} has weight {enregistrement.get('weight')!r}, the "
                f"recipe asks for {poids}."
            ),
            fr=(
                f"Le serveur {nom} a le poids {enregistrement.get('weight')!r}, "
                f"la recette demande {poids}."
            ),
        )
        # L7OK prouve que la sonde a lu une REPONSE, donc qu'elle est
        # applicative. Un `check` seul rend L4OK : il verifie qu'un port
        # accepte, ce que fait aussi un service qui a perdu sa base.
        assert enregistrement.get("check_status") == "L7OK", message(
            en=(
                f"Server {nom} reports check_status "
                f"{enregistrement.get('check_status')!r}, expected L7OK. A bare "
                f"`check` only opens a connection; the recipe asks for the probe "
                f"{recette['sonde']} to be read."
            ),
            fr=(
                f"Le serveur {nom} rapporte check_status "
                f"{enregistrement.get('check_status')!r}, on attend L7OK. Un "
                f"`check` seul ouvre une connexion ; la recette demande que la "
                f"sonde {recette['sonde']} soit lue."
            ),
        )

    total_poids = sum(recette["poids"].values())
    nombre = 20 * total_poids
    comptes = _echantillon(poste, ip_edge, nombre)
    erreurs = {c: n for c, n in comptes.items() if c.startswith("erreur")}
    assert not erreurs, message(
        en=f"Errors on a healthy state: {erreurs}.",
        fr=f"Des erreurs sur un état sain : {erreurs}.",
    )
    for nom, poids in recette["poids"].items():
        attendu = nombre * poids // total_poids
        obtenu = comptes.get(nom, 0)
        assert abs(obtenu - attendu) <= 1 + nombre // 20, message(
            en=(
                f"Server {nom} took {obtenu} of {nombre} requests, its weight "
                f"{poids} of {total_poids} gives it about {attendu}. Full "
                f"sample: {comptes}."
            ),
            fr=(
                f"Le serveur {nom} a pris {obtenu} requêtes sur {nombre}, son "
                f"poids {poids} sur {total_poids} lui en donne environ "
                f"{attendu}. Échantillon complet : {comptes}."
            ),
        )


def test_un_backend_non_pret_est_retire_dans_la_fenetre(
    edge, poste, ip_edge, recette
) -> None:
    """Le retrait a lieu, et c'est UNE descente, pas un état constaté."""
    avant = _table(edge, recette)["beta"]
    descentes_avant = _entier(avant, "chkdown")

    assert not {
        c: n for c, n in _echantillon(poste, ip_edge, 20).items()
        if c.startswith("erreur")
    }, message(
        en="Errors before anything was broken: the starting state is not healthy.",
        fr="Des erreurs avant toute panne : l'état de départ n'est pas sain.",
    )

    fenetre = recette["fall"] * recette["inter"] + 8
    _etat_backend(edge, recette, "beta", "casse")
    try:
        retire = _attendre(
            lambda: _statut(_table(edge, recette)["beta"]) != "UP",
            fenetre,
        )
        apres = _table(edge, recette)["beta"]
        assert retire, message(
            en=(
                f"Server beta is still {apres.get('status')!r} {fenetre}s after "
                f"its readiness started failing. With fall={recette['fall']} and "
                f"inter={recette['inter']}s the removal must happen inside that "
                "window."
            ),
            fr=(
                f"Le serveur beta est encore {apres.get('status')!r} "
                f"{fenetre} s après le début de l'échec de sa readiness. Avec "
                f"fall={recette['fall']} et inter={recette['inter']} s, le "
                "retrait doit avoir lieu dans cette fenêtre."
            ),
        )
        assert _entier(apres, "chkdown") == descentes_avant + 1, message(
            en=(
                f"HAProxy counts {_entier(apres, 'chkdown')} down transitions "
                f"for beta, expected {descentes_avant + 1}. More than one means "
                "the server went down, came back and fell again: the thresholds "
                "are oscillating."
            ),
            fr=(
                f"HAProxy compte {_entier(apres, 'chkdown')} descentes pour "
                f"beta, on en attend {descentes_avant + 1}. Plus d'une signifie "
                "que le serveur est tombé, revenu, et retombé : les seuils "
                "oscillent."
            ),
        )

        comptes = _echantillon(poste, ip_edge, 40)
        assert comptes.get("beta", 0) == 0, message(
            en=(
                f"After convergence, {comptes.get('beta')} requests still "
                f"reached beta. Full sample: {comptes}."
            ),
            fr=(
                f"Après convergence, {comptes.get('beta')} requêtes atteignent "
                f"encore beta. Échantillon complet : {comptes}."
            ),
        )
        erreurs = {c: n for c, n in comptes.items() if c.startswith("erreur")}
        assert not erreurs, message(
            en=(
                f"After convergence, the client still sees errors: {erreurs}. "
                "Removing a backend is only useful if what remains serves "
                "everything."
            ),
            fr=(
                f"Après convergence, le client voit encore des erreurs : "
                f"{erreurs}. Retirer un backend ne sert que si ce qui reste sert "
                "tout."
            ),
        )
    finally:
        _etat_backend(edge, recette, "beta", "pret")

    retour = recette["rise"] * recette["inter"] + 12
    revenu = _attendre(
        lambda: _statut(_table(edge, recette)["beta"]) == "UP", retour
    )
    assert revenu, message(
        en=(
            f"Server beta did not come back within {retour}s after its "
            f"readiness was restored. With rise={recette['rise']} and "
            f"inter={recette['inter']}s it should."
        ),
        fr=(
            f"Le serveur beta n'est pas revenu dans les {retour} s qui ont suivi "
            f"le rétablissement de sa readiness. Avec rise={recette['rise']} et "
            f"inter={recette['inter']} s, il devrait."
        ),
    )


def test_une_panne_plus_courte_que_le_seuil_ne_retire_rien(
    edge, poste, ip_edge, recette
) -> None:
    """LE CONTRE-TEST. Sans lui, `fall 1` passerait le contrôle précédent.

    Une sonde réglée trop court transforme chaque hoquet en bascule, et la
    bascule coûte plus que le hoquet : les connexions en cours sont coupées,
    le serveur restant prend tout, et la charge qu'il encaisse peut le faire
    tomber à son tour.

    La mesure porte sur les deux compteurs de HAProxy. Des sondes doivent
    avoir échoué, sinon la panne n'a pas été vue et le test ne mesure rien ;
    et aucune descente ne doit avoir eu lieu.
    """
    avant = _table(edge, recette)["beta"]
    assert _statut(avant) == "UP", message(
        en=f"Server beta is {avant.get('status')!r}: nothing to measure.",
        fr=f"Le serveur beta est {avant.get('status')!r} : rien à mesurer.",
    )
    echecs_avant = _entier(avant, "chkfail")
    descentes_avant = _entier(avant, "chkdown")

    # Une panne de (fall - 2) sondes : assez pour que des sondes echouent,
    # pas assez pour atteindre le seuil. Les deux bornes sont calculees
    # depuis la recette, donc elles suivent si les seuils changent.
    courte = max(1, (recette["fall"] - 2) * recette["inter"])
    _etat_backend(edge, recette, "beta", "casse")
    time.sleep(courte)
    _etat_backend(edge, recette, "beta", "pret")

    time.sleep(recette["rise"] * recette["inter"] + 3)
    apres = _table(edge, recette)["beta"]

    assert _entier(apres, "chkfail") > echecs_avant, message(
        en=(
            f"No probe failed during the {courte}s dip (chkfail stayed at "
            f"{echecs_avant}). Either the probe is slower than the dip, or it "
            "does not read the readiness endpoint: the test measured nothing."
        ),
        fr=(
            f"Aucune sonde n'a échoué pendant la baisse de {courte} s (chkfail "
            f"est resté à {echecs_avant}). Soit la sonde est plus lente que la "
            "baisse, soit elle ne lit pas la readiness : le test n'a rien "
            "mesuré."
        ),
    )
    assert _entier(apres, "chkdown") == descentes_avant, message(
        en=(
            f"Server beta was taken out during a {courte}s dip (chkdown went "
            f"from {descentes_avant} to {_entier(apres, 'chkdown')}), while the "
            f"recipe asks for fall={recette['fall']} at inter="
            f"{recette['inter']}s, so {recette['fall'] * recette['inter']}s "
            "before removal. A probe tuned too short turns every hiccup into a "
            "switchover."
        ),
        fr=(
            f"Le serveur beta a été retiré sur une baisse de {courte} s (chkdown "
            f"est passé de {descentes_avant} à {_entier(apres, 'chkdown')}), "
            f"alors que la recette demande fall={recette['fall']} à inter="
            f"{recette['inter']} s, donc "
            f"{recette['fall'] * recette['inter']} s avant retrait. Une sonde "
            "réglée trop court transforme chaque hoquet en bascule."
        ),
    )
    assert _statut(apres) == "UP", message(
        en=f"Server beta is {apres.get('status')!r} after a dip it survived.",
        fr=f"Le serveur beta est {apres.get('status')!r} après une baisse qu'il a passée.",
    )


def test_le_drainage_arrete_les_nouvelles_affectations_sans_couper_l_etabli(
    edge, poste, ip_edge, recette
) -> None:
    """Drainer n'est pas arrêter, et la différence se mesure sur un flux ouvert.

    POURQUOI ALPHA EST DRAINE D'ABORD

    Le flux long doit atterrir sur beta, et avec des poids 3 contre 1 une
    connexion sur quatre y va : ouvrir au hasard et réessayer serait long et
    parfois faux. On se sert donc du mécanisme lui-même : alpha drainé, la
    connexion ne peut aller que chez beta. C'est déterministe, et ça utilise
    précisément ce que le contrôle mesure.
    """
    # CE TEST DOIT DEPENDRE DU TRAVAIL, et il n'en dependait pas.
    #
    # Drainer par le socket est une capacite NATIVE de HAProxy : elle marche
    # sans qu'aucune sonde soit configuree, donc sans que l'apprenant ait rien
    # fait. Mesure du 2026-10-26 : ce test passait sur l'etat de depart, et
    # seul un defaut de son propre nettoyage (un `pkill -f` qui tuait sa
    # session) le faisait echouer. Corriger le nettoyage a revele le faux
    # positif, et le lab s'est mis a donner 25 points a vide.
    #
    # Ce qui est demande par la recette, ce sont les SONDES et les POIDS. On
    # l'exige donc avant de mesurer le drainage : sans eux, la demonstration
    # qui suit ne porterait sur rien.
    depart = _table(edge, recette)
    for nom, poids_attendu in recette["poids"].items():
        enregistrement = depart.get(nom, {})
        assert enregistrement.get("check_status") == "L7OK", message(
            en=(
                f"Server {nom} reports check_status "
                f"{enregistrement.get('check_status')!r} instead of L7OK. "
                "Draining is measured on a backend whose probes work: without "
                "them, what follows would prove nothing about your work."
            ),
            fr=(
                f"Le serveur {nom} rapporte check_status "
                f"{enregistrement.get('check_status')!r} au lieu de L7OK. Le "
                "drainage se mesure sur un backend dont les sondes "
                "fonctionnent : sans elles, ce qui suit ne prouverait rien de "
                "votre travail."
            ),
        )
        assert enregistrement.get("weight") == str(poids_attendu), message(
            en=(
                f"Server {nom} carries weight {enregistrement.get('weight')!r}, "
                f"the recipe declares {poids_attendu}. This test relies on "
                "those weights to make the flow land where it must."
            ),
            fr=(
                f"Le serveur {nom} porte le poids "
                f"{enregistrement.get('weight')!r}, la recette déclare "
                f"{poids_attendu}. Ce test s'appuie sur ces poids pour que le "
                "flux atterrisse où il doit."
            ),
        )

    _piloter(edge, recette, f"set server {recette['backend']}/alpha state drain")
    try:
        poste.run("rm -f /tmp/flux-sante.txt")
        poste.run(
            f"nohup flux-long {ip_edge} /tmp/flux-sante.txt "
            ">/dev/null 2>&1 &"
        )
        # Le lambda DIFFÈRE l'appel : `_attendre` rejoue sa condition tant
        # qu'elle est fausse, donc le `poste.run` doit repartir à chaque tour.
        # Le correctif que propose ruff (passer `.stdout.strip`) exécuterait la
        # commande UNE fois, puis redécouperait indéfiniment le même texte :
        # l'attente ne mesurerait plus rien. Ruff le signale lui-même comme un
        # correctif risqué.
        premiere = _attendre(
            lambda: poste.run("head -1 /tmp/flux-sante.txt").stdout.strip(),  # noqa: PLW0108
            20,
        )
        assert premiere and "beta" in premiere, message(
            en=(
                f"The long flow did not land on beta (first line: {premiere!r}) "
                "while alpha was drained. A drained server must take no new "
                "connection."
            ),
            fr=(
                f"Le flux long n'a pas atterri sur beta (première ligne : "
                f"{premiere!r}) alors qu'alpha était drainé. Un serveur drainé "
                "ne doit prendre aucune nouvelle connexion."
            ),
        )
    finally:
        _piloter(edge, recette, f"set server {recette['backend']}/alpha state ready")

    _attendre(lambda: _statut(_table(edge, recette)["alpha"]) == "UP", 15)

    lignes_avant = int(
        poste.run("wc -l < /tmp/flux-sante.txt").stdout.strip() or 0
    )
    _piloter(edge, recette, f"set server {recette['backend']}/beta state drain")
    try:
        etat = _attendre(
            lambda: _statut(_table(edge, recette)["beta"]) == "DRAIN",
            15,
        )
        assert etat, message(
            en=(
                "Server beta is "
                f"{_table(edge, recette)['beta'].get('status')!r} after `set "
                "server ... state drain`, expected DRAIN."
            ),
            fr=(
                "Le serveur beta est "
                f"{_table(edge, recette)['beta'].get('status')!r} après `set "
                "server ... state drain`, on attend DRAIN."
            ),
        )

        comptes = _echantillon(poste, ip_edge, 40)
        assert comptes.get("beta", 0) == 0, message(
            en=(
                f"{comptes.get('beta')} new requests reached a drained beta. "
                f"Full sample: {comptes}."
            ),
            fr=(
                f"{comptes.get('beta')} nouvelles requêtes ont atteint un beta "
                f"drainé. Échantillon complet : {comptes}."
            ),
        )
        erreurs = {c: n for c, n in comptes.items() if c.startswith("erreur")}
        assert not erreurs, message(
            en=f"Draining produced client errors: {erreurs}.",
            fr=f"Le drainage a produit des erreurs client : {erreurs}.",
        )

        # LA MOITIE QUI COMPTE : le flux etabli sur beta continue. C'est toute
        # la difference entre drainer et arreter, et c'est elle qui permet une
        # maintenance sans coupure visible.
        avance = _attendre(
            lambda: int(poste.run("wc -l < /tmp/flux-sante.txt").stdout.strip() or 0)
            > lignes_avant + 2,
            20,
        )
        assert avance, message(
            en=(
                "The flow established on beta stopped receiving as soon as beta "
                "was drained. Draining is not stopping: a drained server keeps "
                "serving what it already holds, which is what makes maintenance "
                "possible without a visible outage."
            ),
            fr=(
                "Le flux établi sur beta a cessé de recevoir dès que beta a été "
                "drainé. Drainer n'est pas arrêter : un serveur drainé continue "
                "de servir ce qu'il tient déjà, et c'est ce qui permet une "
                "maintenance sans coupure visible."
            ),
        )
        contenu = poste.run("cat /tmp/flux-sante.txt").stdout
        assert "erreur:" not in contenu, message(
            en=f"The established flow reported an error: {contenu.strip()[-160:]!r}.",
            fr=f"Le flux établi a signalé une erreur : {contenu.strip()[-160:]!r}.",
        )
    finally:
        _piloter(edge, recette, f"set server {recette['backend']}/beta state ready")
        # `[f]lux-long` et non `flux-long` : `pkill -f` compare le motif a la
        # LIGNE DE COMMANDE COMPLETE de chaque processus, y compris celle du
        # shell qui porte le pkill. Ecrit en clair, le motif se trouve
        # lui-meme, tue son propre parent, et la session SSH meurt avec lui :
        # testinfra remonte alors un code 255 et leve, si bien que le
        # NETTOYAGE du test le faisait echouer. Mesure du 2026-10-26. Les
        # crochets ne changent rien a ce que l'expression reconnait, mais la
        # ligne du pkill ne correspond plus a son propre motif.
        poste.run("pkill -f '[f]lux-long' || true")
