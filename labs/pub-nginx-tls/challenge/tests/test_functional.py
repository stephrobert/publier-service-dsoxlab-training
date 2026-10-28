"""Verify the certificate chain and SANs, an automatic renewal that keeps the
ACME account, key permissions, and TLS surviving a reload then a reboot.

POURQUOI LA VALIDATION APPELLE UN SCRIPT QU'ELLE NE CONNAIT PAS

Le renouvellement peut se faire par une minuterie systemd, par cron, par un
hook du client ACME. Exiger l'un de ces mecanismes reviendrait a noter un
choix d'implementation plutot qu'un resultat. Le scenario demande donc un
point d'entree, `/usr/local/bin/renouveler-certificats`, et la validation
l'appelle : ce qu'elle mesure est la NOUVELLE SERIE REELLEMENT SERVIE, pas
la facon dont elle a ete obtenue.

LE DERNIER TEST COUPE LA MACHINE, et il est donc place en dernier.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
WORK = "/opt/pub-nginx-tls"
NOMS = ("app.lab.test", "api.lab.test")
RENOUVELER = "/usr/local/bin/renouveler-certificats"


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
def racine(edge, tmp_path_factory):
    """L'autorite racine de Pebble, RECUPEREE et non supposee.

    Elle change a chaque demarrage de Pebble : l'ecrire en dur dans le test
    le rendrait faux au premier redemarrage du banc.
    """
    chemin = "/tmp/pub-nginx-tls-racine.pem"
    edge.run(
        f"curl -sk https://127.0.0.1:15000/roots/0 -o {chemin} && chmod 0644 {chemin}"
    )
    return chemin


def _serie(edge, nom: str, racine: str) -> str:
    """Le numero de serie du certificat REELLEMENT servi pour ce nom."""
    res = edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
        f"-CAfile {racine} 2>/dev/null | openssl x509 -noout -serial"
    )
    return res.stdout.strip().split("=", 1)[-1] if "=" in res.stdout else ""



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

def test_la_chaine_et_les_san_des_deux_noms_sont_valides(
    edge, poste, ip_edge, racine
) -> None:
    """CRITIQUE. Le client VALIDE, il ne se contente pas de se connecter.

    `-k` serait ici une faute : ce qui se mesure est justement que la chaine
    remonte a l'autorite et que le nom demande figure dans le certificat.
    """
    # Le client recupere la racine LUI-MEME, depuis l'API de gestion de
    # Pebble, qui ecoute sur toutes les adresses. Transferer le fichier
    # depuis le depot demanderait un heredoc assemble en Python, fragile, et
    # mesurerait accessoirement notre capacite a copier un fichier.
    poste.run(
        f"curl -sk --max-time 10 https://{ip_edge}:15000/roots/0 "
        "-o /tmp/racine-lab.pem"
    )
    presente = poste.run("grep -c 'BEGIN CERTIFICATE' /tmp/racine-lab.pem")
    assert presente.stdout.strip() not in ("", "0"), message(
        en="The lab authority root could not be fetched from the client.",
        fr="La racine de l'autorité du lab n'a pas pu être récupérée depuis le "
        "client.",
    )

    echecs = []
    for nom in NOMS:
        res = poste.run(
            f"curl -sS --max-time 10 --cacert /tmp/racine-lab.pem "
            f"--resolve {nom}:443:{ip_edge} -o /dev/null "
            f"-w '%{{http_code}}' https://{nom}/"
        )
        if res.rc != 0 or res.stdout.strip() != "200":
            echecs.append(
                f"{nom} : curl {res.rc}, HTTP {res.stdout.strip()!r}, "
                f"{(res.stderr or '').strip()[:120]}"
            )
    assert not echecs, message(
        en=(
            "The client could not validate the chain for both names: "
            + " ; ".join(echecs)
            + ". The certificate must be issued by the lab authority and carry "
            "both names in its SANs."
        ),
        fr=(
            "Le client n'a pas pu valider la chaîne pour les deux noms : "
            + " ; ".join(echecs)
            + ". Le certificat doit être émis par l'autorité du lab et porter "
            "les deux noms dans ses SAN."
        ),
    )


def test_le_renouvellement_sert_une_nouvelle_serie_sans_perdre_le_compte(
    edge, racine
) -> None:
    """Trois exigences en une : nouvelle serie, pas de restart, compte conserve.

    Effacer le compte ACME pour repartir de zero marche, et c'est
    precisement ce qu'il ne faut pas faire : chaque creation de compte
    consomme un quota chez une autorite reelle, et perd l'historique.
    """
    entree = edge.run(f"test -x {RENOUVELER}")
    assert entree.rc == 0, message(
        en=(
            f"{RENOUVELER} is missing or not executable. The validation needs "
            "an entry point to trigger a renewal without knowing which "
            "mechanism you chose."
        ),
        fr=(
            f"{RENOUVELER} est absent ou non exécutable. La validation a besoin "
            "d'un point d'entrée pour déclencher un renouvellement sans "
            "connaître le mécanisme que vous avez choisi."
        ),
    )

    avant = _serie(edge, NOMS[0], racine)
    assert avant, message(
        en="No certificate is being served: nothing to renew.",
        fr="Aucun certificat n'est servi : il n'y a rien à renouveler.",
    )
    pid_avant = edge.run("systemctl show -p MainPID --value nginx").stdout.strip()
    compte_avant = edge.run(
        f"sudo find {WORK}/lego/accounts -name '*.json' -printf '%p %s\\n' "
        "2>/dev/null | sort"
    ).stdout.strip()

    resultat = edge.run(f"sudo {RENOUVELER}")
    time.sleep(3)

    apres = _serie(edge, NOMS[0], racine)
    assert apres and apres != avant, message(
        en=(
            f"The served serial did not change ({avant!r} then {apres!r}). The "
            "renewal either did not happen or was not made to be served: "
            f"{(resultat.stdout + resultat.stderr).strip()[-250:]}"
        ),
        fr=(
            f"La série servie n'a pas changé ({avant!r} puis {apres!r}). Le "
            "renouvellement n'a pas eu lieu, ou n'a pas été mis en service : "
            f"{(resultat.stdout + resultat.stderr).strip()[-250:]}"
        ),
    )

    pid_apres = edge.run("systemctl show -p MainPID --value nginx").stdout.strip()
    assert pid_apres == pid_avant, message(
        en=(
            f"Nginx was restarted ({pid_avant} then {pid_apres}). A renewal is "
            "put in service with a reload, which keeps live connections."
        ),
        fr=(
            f"Nginx a été redémarré ({pid_avant} puis {pid_apres}). Un "
            "renouvellement se met en service par un reload, qui conserve les "
            "connexions en cours."
        ),
    )

    compte_apres = edge.run(
        f"sudo find {WORK}/lego/accounts -name '*.json' -printf '%p %s\\n' "
        "2>/dev/null | sort"
    ).stdout.strip()
    assert compte_apres == compte_avant and compte_apres, message(
        en=(
            "The ACME account changed during the renewal. Re-registering works "
            "and must not be the answer: against a real authority it burns a "
            "quota and loses the history. Reuse the account on disk."
        ),
        fr=(
            "Le compte ACME a changé pendant le renouvellement. Se réinscrire "
            "fonctionne et ne doit pas être la réponse : face à une autorité "
            "réelle, cela consomme un quota et perd l'historique. Réutilisez le "
            "compte présent sur le disque."
        ),
    )


def test_les_cles_ne_sont_lisibles_que_par_les_acteurs_prevus(edge) -> None:
    """CRITIQUE, et les deux moities : protege, ET toujours servi.

    Une cle privee lisible par tout compte de la machine ne protege plus
    rien : qui la lit se fait passer pour le service.
    """
    ouverts = edge.run(
        f"sudo find {WORK}/lego -type f \\( -name '*.key' -o -name '*.json' \\) "
        "-perm -o=r -printf '%M %p\\n'"
    ).stdout.strip()
    assert not ouverts, message(
        en=(
            "These private keys or account files are readable by everyone on "
            f"the machine:\n{ouverts}\nWhoever reads the key can impersonate "
            "the service."
        ),
        fr=(
            "Ces clés privées ou fichiers de compte sont lisibles par tout le "
            f"monde sur la machine :\n{ouverts}\nQui lit la clé se fait passer "
            "pour le service."
        ),
    )

    sert = edge.run(
        "curl -s -o /dev/null -w '%{http_code}' --max-time 10 -k "
        "--resolve app.lab.test:443:127.0.0.1 https://app.lab.test/"
    ).stdout.strip()
    assert sert == "200", message(
        en=(
            f"TLS no longer answers (HTTP {sert!r}). Closing the permissions "
            "must not take the service with it: Nginx reads the key as root at "
            "startup, so it does not need the key to be world-readable."
        ),
        fr=(
            f"TLS ne répond plus (HTTP {sert!r}). Fermer les droits ne doit pas "
            "emporter le service : Nginx lit la clé en root au démarrage, il "
            "n'a donc pas besoin qu'elle soit lisible par tous."
        ),
    )


def test_tls_reste_correct_apres_reload_puis_reboot(edge, poste, ip_edge, racine) -> None:
    """CRITIQUE, et dernier : il coupe la machine.

    Un reload d'abord, un reboot ensuite. Le premier verifie qu'on n'a pas
    bricole en memoire ; le second, que rien ne depend d'une commande jouee
    a la main.
    """
    edge.run("sudo nginx -t && sudo systemctl reload nginx")
    time.sleep(2)
    assert _serie(edge, NOMS[0], racine), message(
        en="TLS broke after a plain reload, before any reboot was attempted.",
        fr="TLS a cassé après un simple reload, avant même d'avoir tenté un "
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

    # Pebble revient avec une NOUVELLE autorite racine : on la recupere de
    # nouveau, au lieu de conclure a tort que le certificat est invalide.
    nouvelle_racine = "/tmp/pub-nginx-tls-racine-apres.pem"
    servie = ""
    limite = time.monotonic() + 150
    while time.monotonic() < limite:
        edge.run(
            f"curl -sk https://127.0.0.1:15000/roots/0 -o {nouvelle_racine} "
            f"&& chmod 0644 {nouvelle_racine}"
        )
        servie = edge.run(
            "curl -s -o /dev/null -w '%{http_code}' --max-time 8 -k "
            "--resolve app.lab.test:443:127.0.0.1 https://app.lab.test/"
        ).stdout.strip()
        if servie == "200":
            break
        time.sleep(5)

    assert servie == "200", message(
        en=(
            f"After the reboot, HTTPS does not answer again by itself (HTTP "
            f"{servie!r}). The certificate and the configuration must be on "
            "disk, and Nginx enabled at boot."
        ),
        fr=(
            f"Après le redémarrage, HTTPS ne répond pas de lui-même (HTTP "
            f"{servie!r}). Le certificat et la configuration doivent être sur "
            "le disque, et Nginx activé au démarrage."
        ),
    )

    # CE QUE CE TEST DOIT LAISSER DERRIERE LUI.
    #
    # Ce qu'il mesure est verifie ci-dessus, et le reste de ce bloc n'y
    # touche pas. Mais le redemarrage a emporte l'autorite DE TEST avec la
    # machine : Pebble garde sa racine d'emission et ses comptes en
    # memoire, et repart vierge. Nginx sert donc un certificat que plus
    # aucune autorite vivante ne signe, et le prochain controle de chaine
    # echoue pour une raison qui n'est pas la sienne.
    #
    # Une autorite reelle ne perd ni sa racine ni ses comptes. On remet
    # donc l'etat en coherence avec l'autorite courante, en appelant le
    # point d'entree que le lab exige de toute facon.
    remise = edge.run("sudo /usr/local/bin/renouveler-certificats")
    assert remise.rc == 0, message(
        en=(
            "After the reboot, the renewal entry point could not put the "
            f"state back in line with the restarted test authority: "
            f"{remise.stderr.strip()[:200]!r}. It must cope with an authority "
            "that lost its root and its accounts, which is what Pebble does "
            "on every restart."
        ),
        fr=(
            "Après le redémarrage, le point d'entrée de renouvellement n'a "
            "pas pu remettre l'état en accord avec l'autorité de test, qui a "
            f"redémarré : {remise.stderr.strip()[:200]!r}. Il doit encaisser "
            "une autorité qui a perdu sa racine et ses comptes, ce que Pebble "
            "fait à chaque démarrage."
        ),
    )
