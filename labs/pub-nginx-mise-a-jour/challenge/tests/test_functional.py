"""Drive the delivery plan and measure between every step: the generation
actually served, availability during the switch, the rollback with its own
certificate, and the whole thing surviving a reboot.

CES TESTS PILOTENT, ILS NE CONSTATENT PAS

La specification demande de comparer au manifeste « a chaque etape ». Un
test qui tourne une fois, a la fin, ne voit qu'un etat final : il ne peut
rien dire d'une sequence, et encore moins de la disponibilite pendant une
bascule, qui ne se mesure pas apres.

La validation joue donc elle-meme les deux executables que l'apprenant a
ecrits, `livrer` et `revenir`, dans l'ordre du plan, et mesure entre chaque
appel. C'est pour cela que le mecanisme de livraison est le livrable, et
non l'etat du service.

CE QUI EST MESURE, ET OU IL EST MESURE

La version SERVIE, depuis le client, et non ce que le disque contient ni ce
qu'un lien symbolique designe. Les trois peuvent differer, et c'est
exactement le defaut que ce lab enseigne : un lien bascule sans
redemarrage laisse l'ancien code en memoire.

L'empreinte du certificat PUBLIE, lue dans la poignee de main. Les deux
generations ont le meme nom de service : rien dans le nom ne dit laquelle
est publiee, donc seule l'empreinte le dit. C'est aussi pour cela que les
corps sont lus avec `-k` : l'identite du pair n'est pas verifiee par curl,
elle est verifiee par la comparaison d'empreinte, qui est plus forte.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
WORK = "/opt/pub-nginx-mise-a-jour"
DEPART = "1.4.2"
LIVREE = "1.5.0"


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
def manifeste(edge):
    """Le manifeste, lu sur la cible et rendu en dictionnaire.

    C'est la reference, et elle vit sur la machine : un test qui porterait
    les empreintes en dur mesurerait sa propre copie.
    """
    texte = edge.file(f"{WORK}/manifeste.txt").content_string
    lu: dict[str, dict[str, str]] = {}
    courante = None
    for ligne in texte.splitlines():
        morceaux = ligne.split()
        if len(morceaux) == 2 and morceaux[0] == "generation":
            courante = morceaux[1]
            lu[courante] = {}
        elif courante and len(morceaux) == 2:
            lu[courante][morceaux[0]] = morceaux[1]
    for version in (DEPART, LIVREE):
        assert lu.get(version, {}).get("empreinte_sha256"), message(
            en=(
                f"The manifest does not give generation {version} a certificate "
                f"fingerprint. Read {WORK}/manifeste.txt: without it nothing "
                "can be compared."
            ),
            fr=(
                f"Le manifeste ne donne pas d'empreinte de certificat à la "
                f"génération {version}. Lisez {WORK}/manifeste.txt : sans elle, "
                "rien n'est comparable."
            ),
        )
    return lu


def _version_servie(poste, ip: str) -> str:
    """Ce que le service REND, depuis le client."""
    return poste.run(
        f"curl -sk --max-time 10 --resolve service.lab.test:443:{ip} "
        f"https://service.lab.test/version"
    ).stdout.strip()


def _empreinte_publiee(poste, ip: str) -> str:
    """L'empreinte du certificat lu dans la poignee de main.

    `sed 's/.*=//'` et non `'s/.*= //'` : openssl n'ecrit pas d'espace apres
    le signe egal (mesure du 2026-10-26, openssl 3 :
    « sha256 Fingerprint=87:D7:... »). Le motif qui en attendait un rendait
    la ligne entiere, des deux cotes de la comparaison, et le manifeste
    pose par la fixture devenait illisible pour le lecteur ci-dessous. Les
    deux endroits se corrigent ensemble : n'en changer qu'un ferait comparer
    une empreinte nue a une ligne de sortie.
    """
    return poste.run(
        f"echo | openssl s_client -connect {ip}:443 "
        f"-servername service.lab.test 2>/dev/null "
        f"| openssl x509 -noout -fingerprint -sha256 | sed 's/^.*=//'"
    ).stdout.strip()


def _lignes(poste, fichier: str) -> list[str]:
    return [
        ligne for ligne in poste.run(f"cat {fichier} 2>/dev/null").stdout.splitlines()
        if ligne.strip()
    ]



def _attendre_retour(machine, limite_s: float = 180.0) -> bool:
    """Attend qu'une machine redemarree reponde de nouveau.

    `testinfra` LEVE quand la connexion SSH echoue, au lieu de rendre un
    resultat en echec. Une machine absente pendant son redemarrage n'est
    pourtant pas une erreur de test : c'est l'etat qu'on attend. On traite
    donc l'exception comme une reponse negative, et on reessaie.

    Mesure du 2026-10-26 : sans cette tolerance, le test echoue en 22
    secondes au lieu d'attendre, sur un `Connection refused` qui signifie
    seulement que sshd n'ecoute pas encore.
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

def test_l_etat_de_depart_est_celui_du_plan_et_les_executables_existent(
    poste, edge, ip_edge, manifeste
) -> None:
    """L'ancrage, et les deux livrables.

    Il passe avant tout le reste parce que tout le reste en depend : la
    validation va JOUER ces deux executables, et une sequence qui part
    d'un etat inconnu ne mesure rien.
    """
    for nom in ("livrer", "revenir"):
        chemin = f"{WORK}/{nom}"
        assert edge.file(chemin).exists, message(
            en=(
                f"{chemin} is missing. The plan asks for two executables: the "
                "validation plays them, it does not inspect a final state. "
                f"Read {WORK}/plan.txt."
            ),
            fr=(
                f"{chemin} est absent. Le plan demande deux exécutables : la "
                "validation les joue, elle n'inspecte pas un état final. "
                f"Lisez {WORK}/plan.txt."
            ),
        )
        assert edge.file(chemin).mode & 0o111, message(
            en=(
                f"{chemin} is not executable (mode "
                f"{oct(edge.file(chemin).mode)}). The language is yours; being "
                "runnable is not optional."
            ),
            fr=(
                f"{chemin} n'est pas exécutable (mode "
                f"{oct(edge.file(chemin).mode)}). Le langage vous appartient ; "
                "être exécutable ne se négocie pas."
            ),
        )

    servie = _version_servie(poste, ip_edge)
    assert servie == DEPART, message(
        en=(
            f"The service serves {servie!r} and not {DEPART}, which is step 1 "
            "of the plan. Bring it back to the posed state before the "
            "validation drives the sequence."
        ),
        fr=(
            f"Le service rend {servie!r} et non {DEPART}, qui est l'étape 1 du "
            "plan. Ramenez-le à l'état posé avant que la validation déroule la "
            "séquence."
        ),
    )
    empreinte = _empreinte_publiee(poste, ip_edge)
    assert empreinte == manifeste[DEPART]["empreinte_sha256"], message(
        en=(
            f"The published certificate has fingerprint {empreinte}, and the "
            f"manifest gives generation {DEPART} "
            f"{manifeste[DEPART]['empreinte_sha256']}. Both certificates carry "
            "the same service name, so only the fingerprint tells them apart."
        ),
        fr=(
            f"Le certificat publié a pour empreinte {empreinte}, et le "
            f"manifeste donne {manifeste[DEPART]['empreinte_sha256']} à la "
            f"génération {DEPART}. Les deux certificats portent le même nom de "
            "service : seule l'empreinte les distingue."
        ),
    )


@pytest.fixture(scope="module")
def livraison(poste, edge, ip_edge):
    """Joue `livrer 1.5.0` en mesurant pendant la bascule.

    Les deux mesures doivent etre EN COURS quand la livraison se joue,
    sans quoi elles ne mesurent rien : la disponibilite pendant une
    bascule ne se constate pas apres.
    """
    poste.run(f"nohup flux-long {ip_edge} /tmp/flux.txt >/dev/null 2>&1 &")
    # Le flux doit avoir commence a recevoir AVANT la bascule, sinon le
    # test ne distingue pas « il a survecu » de « il n'avait pas commence ».
    avant = 0
    limite = time.monotonic() + 20
    while time.monotonic() < limite:
        avant = len(_lignes(poste, "/tmp/flux.txt"))
        if avant >= 2:
            break
        time.sleep(1)

    poste.run(
        f"nohup sonde-courte {ip_edge} /tmp/sonde.txt 45 >/dev/null 2>&1 &"
    )
    time.sleep(2)

    resultat = edge.run(f"sudo {WORK}/livrer {LIVREE}")

    # On attend la fin de la sonde plutot que de la tuer : une serie
    # tronquee ferait baisser le nombre d'erreurs sans rien prouver.
    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        if "fin" in _lignes(poste, "/tmp/sonde.txt"):
            break
        time.sleep(2)
    codes = [c for c in _lignes(poste, "/tmp/sonde.txt") if c != "fin"]

    time.sleep(6)
    apres = len(_lignes(poste, "/tmp/flux.txt"))

    return {
        "sortie": resultat,
        "codes": codes,
        "flux_avant": avant,
        "flux_apres": apres,
    }


def test_la_livraison_amene_la_version_et_le_certificat_du_manifeste(
    poste, ip_edge, manifeste, livraison
) -> None:
    """L'etape 2, mesuree la ou le service repond."""
    assert livraison["sortie"].rc == 0, message(
        en=(
            f"`livrer {LIVREE}` exited with {livraison['sortie'].rc}. Its "
            f"output was:\n{livraison['sortie'].stdout}\n"
            f"{livraison['sortie'].stderr}"
        ),
        fr=(
            f"`livrer {LIVREE}` est sorti en {livraison['sortie'].rc}. Sa "
            f"sortie était :\n{livraison['sortie'].stdout}\n"
            f"{livraison['sortie'].stderr}"
        ),
    )

    servie = _version_servie(poste, ip_edge)
    assert servie == LIVREE, message(
        en=(
            f"After `livrer {LIVREE}`, the service still serves {servie!r}. "
            "What is installed, what a symlink points at and what is running "
            "are three different things: a generation swapped on disk without "
            "the process being replaced leaves the old code in memory."
        ),
        fr=(
            f"Après `livrer {LIVREE}`, le service rend encore {servie!r}. Ce "
            "qui est installé, ce qu'un lien symbolique désigne et ce qui "
            "tourne sont trois choses différentes : une génération basculée sur "
            "le disque sans que le processus soit remplacé laisse l'ancien code "
            "en mémoire."
        ),
    )

    empreinte = _empreinte_publiee(poste, ip_edge)
    assert empreinte == manifeste[LIVREE]["empreinte_sha256"], message(
        en=(
            f"The published certificate has fingerprint {empreinte}, and the "
            f"manifest gives generation {LIVREE} "
            f"{manifeste[LIVREE]['empreinte_sha256']}. A delivery brings the "
            "generation's code and its certificate, and the service name does "
            "not change between the two."
        ),
        fr=(
            f"Le certificat publié a pour empreinte {empreinte}, et le "
            f"manifeste donne {manifeste[LIVREE]['empreinte_sha256']} à la "
            f"génération {LIVREE}. Une livraison amène le code de la génération "
            "ET son certificat, et le nom du service ne change pas entre les "
            "deux."
        ),
    )


def test_la_bascule_ne_coupe_ni_le_trafic_court_ni_le_flux_long(
    poste, edge, livraison
) -> None:
    """La mesure de disponibilite, prise PENDANT la livraison.

    ELLE EXIGE D'ABORD QUE LA BASCULE AIT EU LIEU, et c'est la correction du
    2026-10-26 : une sonde qui ne releve aucune erreur pendant une
    livraison qui n'a pas eu lieu ne mesure rien du tout. Sur l'etat de
    depart, ou `livrer` n'existe meme pas, le service ne bouge pas, donc la
    serie est parfaite et ce test passait AVANT tout travail.
    """
    assert livraison["sortie"].rc == 0, message(
        en=(
            f"`livrer {LIVREE}` exited with {livraison['sortie'].rc}, so no "
            "switch happened: there is no availability to measure. Its output "
            f"was:\n{livraison['sortie'].stdout}\n{livraison['sortie'].stderr}"
        ),
        fr=(
            f"`livrer {LIVREE}` est sorti en {livraison['sortie'].rc} : aucune "
            "bascule n'a eu lieu, il n'y a donc aucune disponibilité à "
            f"mesurer. Sa sortie était :\n{livraison['sortie'].stdout}\n"
            f"{livraison['sortie'].stderr}"
        ),
    )

    codes = livraison["codes"]
    assert len(codes) >= 20, message(
        en=(
            f"The continuous probe only collected {len(codes)} answers: the "
            "series is too short to say anything about the switch."
        ),
        fr=(
            f"La sonde continue n'a recueilli que {len(codes)} réponses : la "
            "série est trop courte pour dire quoi que ce soit de la bascule."
        ),
    )
    rates = [c for c in codes if c != "200"]
    assert len(rates) <= 1, message(
        en=(
            f"{len(rates)} of {len(codes)} probe requests failed during the "
            f"delivery ({sorted(set(rates))}). The two generations have their "
            "own ports and can run at the same time: start the new one, wait "
            "until it answers, point the proxy at it, reload. Stopping before "
            "starting opens a window nothing closes."
        ),
        fr=(
            f"{len(rates)} requêtes de sonde sur {len(codes)} ont échoué "
            f"pendant la livraison ({sorted(set(rates))}). Les deux générations "
            "ont chacune leur port et peuvent tourner en même temps : démarrez "
            "la nouvelle, attendez qu'elle réponde, faites pointer le proxy "
            "dessus, rechargez. Arrêter avant de démarrer ouvre une fenêtre que "
            "rien ne referme."
        ),
    )

    assert livraison["flux_avant"] >= 2, message(
        en=(
            "The long flow had not started receiving before the switch "
            f"({livraison['flux_avant']} lines): its survival cannot be "
            "measured. Check that /flux answers and is not buffered."
        ),
        fr=(
            "Le flux long n'avait pas commencé à recevoir avant la bascule "
            f"({livraison['flux_avant']} lignes) : sa survie ne peut pas être "
            "mesurée. Vérifiez que /flux répond et n'est pas mis en tampon."
        ),
    )
    assert livraison["flux_apres"] > livraison["flux_avant"], message(
        en=(
            f"The long flow stopped at {livraison['flux_avant']} lines and "
            f"received nothing more after the switch ({livraison['flux_apres']} "
            "in total). A delivery does not cut the previous generation: it is "
            "the NEXT delivery that removes it, once it has nothing left to "
            "serve. Reloading the proxy keeps established connections on the "
            "old workers; stopping the old backend kills them anyway."
        ),
        fr=(
            f"Le flux long s'est arrêté à {livraison['flux_avant']} lignes et "
            f"n'a plus rien reçu après la bascule ({livraison['flux_apres']} au "
            "total). Une livraison ne coupe pas la génération précédente : "
            "c'est la livraison SUIVANTE qui la retire, quand elle n'a plus "
            "rien à servir. Recharger le proxy garde les connexions établies "
            "sur les anciens workers ; arrêter l'ancien backend les tue quand "
            "même."
        ),
    )


def test_le_journal_de_livraison_existe_et_parle_du_flux_long(edge) -> None:
    """Ce que la machine juge du journal : sa presence, et son sujet.

    Pas sa qualite. Un controle qui noterait une explication noterait en
    realite la presence de mots-clefs, et apprendrait a en semer. Le texte
    se lit.
    """
    chemin = f"{WORK}/journal.md"
    assert edge.file(chemin).exists, message(
        en=(
            f"{chemin} is missing. The plan asks for your measurements and "
            "what you conclude from them: how many failures on short traffic, "
            "what happened to the long flow, and why."
        ),
        fr=(
            f"{chemin} est absent. Le plan demande vos mesures et ce que vous "
            "en concluez : combien d'échecs sur le trafic court, ce qui est "
            "arrivé au flux long, et pourquoi."
        ),
    )
    texte = edge.file(chemin).content_string
    assert len(texte.strip()) >= 150, message(
        en=f"The delivery log holds {len(texte.strip())} characters: too short "
           "to carry a measurement and its explanation.",
        fr=f"Le journal de livraison contient {len(texte.strip())} caractères : "
           "trop court pour porter une mesure et son explication.",
    )
    minuscule = texte.lower()
    assert "flux" in minuscule or "flow" in minuscule, message(
        en=(
            "The delivery log does not mention the long flow. It is the part a "
            "reload treats differently from short traffic, and the part worth "
            "writing down."
        ),
        fr=(
            "Le journal de livraison ne parle pas du flux long. C'est "
            "précisément ce qu'un rechargement traite autrement que le trafic "
            "court, et c'est ce qui vaut d'être écrit."
        ),
    )


def test_le_retour_arriere_restaure_la_version_et_son_certificat(
    poste, edge, ip_edge, manifeste, livraison
) -> None:
    """CRITIQUE. L'etape 3 : revenir, avec le certificat de la generation.

    Le piege est de ne ramener que le code. Les deux certificats portent le
    meme nom de service, donc un retour arriere qui oublie le certificat
    n'a l'air de rien : le service repond, le nom est bon, et l'empreinte
    est celle de la generation qu'on vient de retirer.
    """
    resultat = edge.run(f"sudo {WORK}/revenir")
    assert resultat.rc == 0, message(
        en=(
            f"`revenir` exited with {resultat.rc}. Its output was:\n"
            f"{resultat.stdout}\n{resultat.stderr}"
        ),
        fr=(
            f"`revenir` est sorti en {resultat.rc}. Sa sortie était :\n"
            f"{resultat.stdout}\n{resultat.stderr}"
        ),
    )

    servie = _version_servie(poste, ip_edge)
    assert servie == DEPART, message(
        en=(
            f"After `revenir`, the service serves {servie!r} and not {DEPART}, "
            "which is the generation that was served before the delivery. "
            "`revenir` needs to know where it came from, and that memory has "
            "to survive a reboot: /run and /tmp do not."
        ),
        fr=(
            f"Après `revenir`, le service rend {servie!r} et non {DEPART}, qui "
            "est la génération servie avant la livraison. `revenir` a besoin de "
            "savoir d'où il vient, et cette mémoire doit survivre à un "
            "redémarrage : /run et /tmp n'en sont pas."
        ),
    )

    empreinte = _empreinte_publiee(poste, ip_edge)
    assert empreinte == manifeste[DEPART]["empreinte_sha256"], message(
        en=(
            f"The code went back to {DEPART} but the published certificate has "
            f"fingerprint {empreinte}, which the manifest gives to the other "
            "generation. A rollback that forgets the certificate looks like "
            "nothing at all: the service answers, the name is right, and only "
            "the fingerprint says the certificate belongs to the generation "
            "that was just withdrawn."
        ),
        fr=(
            f"Le code est bien revenu en {DEPART}, mais le certificat publié a "
            f"pour empreinte {empreinte}, que le manifeste attribue à l'autre "
            "génération. Un retour arrière qui oublie le certificat n'a l'air "
            "de rien : le service répond, le nom est bon, et seule l'empreinte "
            "dit que le certificat est celui de la génération qu'on vient de "
            "retirer."
        ),
    )


def test_la_recette_passe_apres_reboot_sans_intervention(
    poste, edge, ip_edge, manifeste
) -> None:
    """CRITIQUE, et dernier : un service livre n'est pas un service lance.

    Ce test coupe la machine. Il est donc place en dernier a dessein : tout
    ce qui le suivrait mesurerait un autre etat que celui que la sequence
    vient d'etablir.

    CE QU'IL EXIGE EN PLUS DEPUIS LE 2026-10-26, et pourquoi

    Que les deux executables soient ENCORE la, et encore executables, apres
    le redemarrage. C'est une propriete du livrable, pas une repetition du
    premier test : un `livrer` ecrit dans /tmp, /run ou /dev/shm passe le
    premier controle et disparait au premier redemarrage. Et c'est aussi ce
    qui empeche ce test de se satisfaire de l'etat de depart, ou la machine
    rend deja 1.4.2 avec son certificat sans que rien ait ete livre : sans
    cette exigence, il pouvait passer AVANT tout travail.
    """
    assert _version_servie(poste, ip_edge) == DEPART, message(
        en="The service must serve the rolled-back generation before the "
           "reboot is attempted.",
        fr="Le service doit rendre la génération restaurée avant de tenter le "
           "redémarrage.",
    )

    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)

    revenu = _attendre_retour(edge, 180)
    assert revenu, message(
        en="edge.lab did not come back online within 180s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180 s après le "
           "redémarrage.",
    )

    # Le service peut mettre quelques secondes a reprendre : on attend, au
    # lieu de conclure sur la premiere tentative.
    servie = ""
    limite = time.monotonic() + 120
    while time.monotonic() < limite:
        servie = _version_servie(poste, ip_edge)
        if servie == DEPART:
            break
        time.sleep(5)
    assert servie == DEPART, message(
        en=(
            f"Two minutes after the reboot, the service serves {servie!r} and "
            f"not {DEPART}. A service that answers today and does not come back "
            "tomorrow is not delivered, it is launched: whatever a delivery "
            "changes has to be enabled at boot and written somewhere that "
            "survives."
        ),
        fr=(
            f"Deux minutes après le redémarrage, le service rend {servie!r} et "
            f"non {DEPART}. Un service qui répond aujourd'hui et ne revient pas "
            "demain n'est pas livré, il est lancé : ce qu'une livraison change "
            "doit être activé au démarrage et écrit à un endroit qui survit."
        ),
    )

    for nom in ("livrer", "revenir"):
        chemin = f"{WORK}/{nom}"
        fichier = edge.file(chemin)
        assert fichier.exists and fichier.mode & 0o111, message(
            en=(
                f"{chemin} did not survive the reboot. A delivery mechanism "
                "written into /tmp, /run or /dev/shm passes once and is gone "
                "the next morning: it has to live where the machine keeps it."
            ),
            fr=(
                f"{chemin} n'a pas survécu au redémarrage. Un mécanisme de "
                "livraison écrit dans /tmp, /run ou /dev/shm passe une fois et "
                "disparaît le lendemain : il doit vivre là où la machine le "
                "garde."
            ),
        )

    empreinte = _empreinte_publiee(poste, ip_edge)
    assert empreinte == manifeste[DEPART]["empreinte_sha256"], message(
        en=(
            f"The service came back on {DEPART} but publishes fingerprint "
            f"{empreinte}, not {manifeste[DEPART]['empreinte_sha256']}. The "
            "code survived the reboot and the certificate did not."
        ),
        fr=(
            f"Le service est bien revenu en {DEPART} mais publie l'empreinte "
            f"{empreinte}, et non {manifeste[DEPART]['empreinte_sha256']}. Le "
            "code a survécu au redémarrage, le certificat non."
        ),
    )
