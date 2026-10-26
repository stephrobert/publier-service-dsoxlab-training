"""Verify that both names validate strictly with their own certificate, that
the learner's renewal script really produces a new one, that invalid material
is refused rather than served, that no private key leaks into any output, and
that all of it survives a reload then a reboot.

CE QUE LE SETUP POSE : l'application publiee en HTTP, une autorite de test
dont les certificats valent cinq minutes, un client ACME externe enveloppe
dans un executable, et AUCUN certificat.

LA VALIDATION EXECUTE LE SCRIPT DE L'APPRENANT

Le deuxieme controle lance `renouveler` et mesure entre deux appels. C'est la
seule facon de mesurer un cycle : un certificat valide constate apres coup ne
dit pas s'il a ete obtenu par un script rejouable ou a la main une fois. Et
un cycle qui ne se rejoue pas n'est pas un cycle, c'est un certificat qui
expirera un jour ou personne ne regardera.

LE CONTRE-TEST DU CHARGEMENT VERIFIE

Le meme controle pousse lui-meme un certificat invalide par le socket. Sans
cette moitie, un `systemctl restart` apres chaque renouvellement passerait :
il charge aussi le nouveau materiel. La difference est qu'il coupe les
connexions en cours, et que sur un materiel casse il laisse le service a
terre, la ou `commit ssl cert` refuse et garde le precedent.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
RECETTE = "/opt/pub-haproxy-tls-stable/recette.txt"
MARQUE = "pub-haproxy-tls-stable service"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


def _valeur(edge, cle: str) -> str:
    valeur = edge.run(f"grep -oP '(?<=^{cle} = ).*' {RECETTE}").stdout.strip()
    assert valeur, message(
        en=f"The recipe {RECETTE} declares no `{cle}`.",
        fr=f"La recette {RECETTE} ne déclare aucun `{cle}`.",
    )
    return valeur


@pytest.fixture(scope="module")
def recette(edge) -> dict[str, str]:
    cles = (
        "nom_a",
        "nom_b",
        "pem_a",
        "pem_b",
        "racine_acme",
        "client_acme",
        "renouveler",
        "socket_admin",
        "port_defi",
        "chemin_defi",
    )
    return {cle: _valeur(edge, cle) for cle in cles}


def _presente(edge, recette, nom: str) -> dict[str, str]:
    """Le certificat REELLEMENT servi pour ce nom, lu par une poignee de main.

    On ne lit pas le fichier PEM du disque : ce qui compte est ce que le
    service presente, et les deux peuvent differer d'exactement un
    rechargement oublie.
    """
    sortie = edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {nom} "
        f"2>/dev/null | openssl x509 -noout -serial -enddate -subject"
    ).stdout
    champs: dict[str, str] = {}
    for ligne in sortie.splitlines():
        if "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            champs[cle.strip()] = valeur.strip()
    assert champs.get("serial"), message(
        en=(
            f"No certificate is served for {nom} on port 443 "
            f"(answer: {sortie.strip()[:160]!r})."
        ),
        fr=(
            f"Aucun certificat n'est servi pour {nom} sur le port 443 "
            f"(réponse : {sortie.strip()[:160]!r})."
        ),
    )
    return champs


def _valider(edge, recette, sni: str, hote: str):
    """Une poignée de main STRICTE : chaîne et nom d'hôte, sans exception."""
    return edge.run(
        f"echo | openssl s_client -connect 127.0.0.1:443 -servername {sni} "
        f"-CAfile {recette['racine_acme']} -verify_hostname {hote} "
        f"-verify_return_error -brief 2>&1"
    )


def _piloter(edge, recette, commande: str):
    return edge.run(
        f"echo '{commande}' | sudo socat -t5 stdio {recette['socket_admin']}"
    )


def _recette_identite(edge, recette) -> None:
    """Les deux noms valident strictement, et chacun a SON certificat."""
    for cle_nom in ("nom_a", "nom_b"):
        nom = recette[cle_nom]
        stricte = _valider(edge, recette, nom, nom)
        assert stricte.rc == 0, message(
            en=(
                f"Strict TLS validation failed for {nom}: "
                f"{stricte.stdout.strip()[:200]!r}. Chain and hostname are "
                "checked against the test authority's root, and verification is "
                "never disabled."
            ),
            fr=(
                f"La validation TLS stricte échoue pour {nom} : "
                f"{stricte.stdout.strip()[:200]!r}. La chaîne et le nom d'hôte "
                "sont vérifiés avec la racine de l'autorité de test, et la "
                "vérification ne se désactive pas."
            ),
        )

        page = edge.run(
            f"curl -sS --cacert {recette['racine_acme']} "
            f"--resolve {nom}:443:127.0.0.1 https://{nom}/ 2>&1"
        ).stdout
        assert MARQUE in page, message(
            en=(
                f"{nom} validates but does not reach the application "
                f"(answer: {page.strip()[:160]!r})."
            ),
            fr=(
                f"{nom} valide mais n'atteint pas l'application "
                f"(réponse : {page.strip()[:160]!r})."
            ),
        )

    # LE CONTRE-TEST. Presenter le certificat d'un nom et le faire valider
    # contre l'autre doit echouer. Sans cette moitie, un certificat unique
    # portant les deux noms en SAN passerait les deux validations strictes
    # ci-dessus, et la selection par SNI ne serait pas mesuree du tout.
    croise = _valider(edge, recette, recette["nom_a"], recette["nom_b"])
    assert croise.rc != 0, message(
        en=(
            f"The certificate served for {recette['nom_a']} also validates "
            f"against {recette['nom_b']}. The recipe asks for one certificate "
            "per name: a single certificate carrying both names passes both "
            "strict checks and leaves SNI selection unmeasured."
        ),
        fr=(
            f"Le certificat servi pour {recette['nom_a']} valide aussi contre "
            f"{recette['nom_b']}. La recette demande un certificat par nom : un "
            "certificat unique portant les deux noms passe les deux "
            "vérifications strictes et laisse la sélection par SNI sans mesure."
        ),
    )



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

def test_les_deux_noms_valident_strictement_avec_leur_propre_certificat(
    edge, recette
) -> None:
    """CRITIQUE : l'identité, et le contre-test qui la rend mesurable."""
    _recette_identite(edge, recette)


def _recette_cycle(edge, recette) -> None:
    """Le script de l'apprenant est EXECUTE, et la mesure se fait entre deux appels."""
    avant = {
        nom: _presente(edge, recette, recette[nom]) for nom in ("nom_a", "nom_b")
    }

    lancement = edge.run(f"sudo {recette['renouveler']} 2>&1")
    assert lancement.rc == 0, message(
        en=(
            f"{recette['renouveler']} failed (code {lancement.rc}): "
            f"{lancement.stdout.strip()[-400:]!r}"
        ),
        fr=(
            f"{recette['renouveler']} a échoué (code {lancement.rc}) : "
            f"{lancement.stdout.strip()[-400:]!r}"
        ),
    )

    for cle_nom in ("nom_a", "nom_b"):
        nom = recette[cle_nom]
        apres = _presente(edge, recette, nom)
        assert apres["serial"] != avant[cle_nom]["serial"], message(
            en=(
                f"{nom} still serves serial {apres['serial']} after "
                f"{recette['renouveler']} ran. The script returned success "
                "without the service presenting new material: either no "
                "certificate was obtained, or it was written to disk and never "
                "loaded."
            ),
            fr=(
                f"{nom} sert encore le numéro de série {apres['serial']} après "
                f"l'exécution de {recette['renouveler']}. Le script a rendu un "
                "succès sans que le service présente du nouveau matériel : soit "
                "aucun certificat n'a été obtenu, soit il a été écrit sur le "
                "disque et jamais chargé."
            ),
        )


def test_le_cycle_produit_un_nouveau_certificat(edge, recette) -> None:
    _recette_cycle(edge, recette)


def test_un_certificat_invalide_est_refuse_et_non_servi(edge, recette) -> None:
    """La seconde moitié du chargement vérifié, et c'est elle qui le qualifie.

    Un `systemctl restart` après chaque renouvellement charge aussi le
    nouveau matériel : il passerait le contrôle précédent. La différence est
    qu'il coupe les connexions en cours, et que sur un matériel cassé il
    laisse le service à terre, là où `commit ssl cert` refuse et garde le
    précédent.
    """
    pem = recette["pem_a"]
    nom = recette["nom_a"]
    avant = _presente(edge, recette, nom)

    # Charge utile volontairement invalide. La syntaxe `<<` du socket prend
    # un bloc termine par une ligne vide : c'est par la que HAProxy recoit un
    # certificat sans qu'il touche le disque.
    charge = "-----BEGIN CERTIFICATE-----\npas un certificat\n-----END CERTIFICATE-----"
    pousse = edge.run(
        f"printf 'set ssl cert {pem} <<\n{charge}\n\n' "
        f"| sudo socat -t5 stdio {recette['socket_admin']} 2>&1"
    )
    try:
        commit = _piloter(edge, recette, f"commit ssl cert {pem}")
        sorties = (pousse.stdout + commit.stdout).lower()
        refuse = commit.rc != 0 or any(
            motif in sorties
            for motif in ("error", "erreur", "unable", "cannot", "invalid", "fail")
        )
        assert refuse, message(
            en=(
                "Invalid certificate material was accepted without a word "
                f"(answers: {pousse.stdout.strip()[:120]!r} then "
                f"{commit.stdout.strip()[:120]!r}). A verified load checks the "
                "material before putting it into service."
            ),
            fr=(
                "Du matériel de certificat invalide a été accepté sans un mot "
                f"(réponses : {pousse.stdout.strip()[:120]!r} puis "
                f"{commit.stdout.strip()[:120]!r}). Un chargement vérifié "
                "contrôle le matériel avant de le mettre en service."
            ),
        )
    finally:
        _piloter(edge, recette, f"abort ssl cert {pem}")

    apres = _presente(edge, recette, nom)
    assert apres["serial"] == avant["serial"], message(
        en=(
            f"{nom} no longer serves the certificate it served before the "
            f"invalid material was pushed ({avant['serial']} then "
            f"{apres['serial']}). A refusal must leave the running certificate "
            "in place."
        ),
        fr=(
            f"{nom} ne sert plus le certificat qu'il servait avant que le "
            f"matériel invalide ne soit poussé ({avant['serial']} puis "
            f"{apres['serial']}). Un refus doit laisser en place le certificat "
            "en service."
        ),
    )
    stricte = _valider(edge, recette, nom, nom)
    assert stricte.rc == 0, message(
        en=(
            f"{nom} no longer validates after an invalid certificate was "
            "refused. Refusing must not take the service with it."
        ),
        fr=(
            f"{nom} ne valide plus après le refus d'un certificat invalide. "
            "Refuser ne doit pas emporter le service."
        ),
    )


def test_les_cles_sont_protegees_et_absentes_des_sorties(edge, recette) -> None:
    """CRITIQUE : une clé dans un journal est une clé publiée.

    La rotation ne la rattrape pas : le journal est collecté, archivé,
    recopié dans un rapport d'incident, et la clé y reste après que le
    certificat a expiré.
    """
    travail = "/opt/pub-haproxy-tls-stable"
    porteurs = edge.run(
        f"sudo grep -rlE 'PRIVATE[ ]KEY' {travail} /etc/haproxy/certs 2>/dev/null"
    ).stdout.split()
    assert porteurs, message(
        en=(
            f"No file carrying a private key was found under {travail} or "
            "/etc/haproxy/certs. Either nothing was obtained, or the material "
            "lives somewhere the recipe does not describe."
        ),
        fr=(
            f"Aucun fichier portant une clé privée n'a été trouvé sous "
            f"{travail} ni /etc/haproxy/certs. Soit rien n'a été obtenu, soit le "
            "matériel vit ailleurs que là où la recette le décrit."
        ),
    )

    for chemin in porteurs:
        droits = edge.run(f"sudo stat -c '%a %U' {chemin}").stdout.split()
        assert droits, message(
            en=f"Cannot read the mode of {chemin}.",
            fr=f"Impossible de lire les droits de {chemin}.",
        )
        mode = int(droits[0], 8)
        assert mode & 0o007 == 0, message(
            en=(
                f"{chemin} carries a private key and is mode {droits[0]}: any "
                "account on the machine can read it."
            ),
            fr=(
                f"{chemin} porte une clé privée et est en mode {droits[0]} : "
                "n'importe quel compte de la machine peut la lire."
            ),
        )

    sentinelles = edge.run(
        "sudo grep -rlE 'PRIVATE[ ]KEY' /var/log 2>/dev/null"
    ).stdout.split()
    assert not sentinelles, message(
        en=(
            f"A private key appears in {sentinelles}. A key in a log is a "
            "published key: the log gets collected, archived and pasted into an "
            "incident report, and the key stays there long after the "
            "certificate expired."
        ),
        fr=(
            f"Une clé privée apparaît dans {sentinelles}. Une clé dans un "
            "journal est une clé publiée : le journal est collecté, archivé, "
            "recopié dans un rapport d'incident, et la clé y reste longtemps "
            "après l'expiration du certificat."
        ),
    )

    dans_le_journal = edge.run(
        "sudo journalctl -b --no-pager 2>/dev/null | grep -cE 'PRIVATE[ ]KEY'"
    ).stdout.strip()
    assert dans_le_journal in ("", "0"), message(
        en=(
            f"The system journal carries {dans_le_journal} lines with private "
            "key material. A renewal script must never print what it writes."
        ),
        fr=(
            f"Le journal systémique porte {dans_le_journal} lignes de matériel "
            "de clé privée. Un script de renouvellement n'imprime jamais ce "
            "qu'il écrit."
        ),
    )


def test_le_cycle_reste_operant_apres_rechargement_puis_redemarrage(
    edge, recette
) -> None:
    """CRITIQUE, et dernier : il coupe la machine, puis RENOUVELLE après.

    Rejouer le cycle après le redémarrage plutôt que de constater une page
    qui répond est ce qui fait la différence. Un cycle qui dépendait d'un
    répertoire sous `/run`, d'un conteneur lancé à la main ou d'une variable
    d'environnement de la session se voit là, et nulle part avant.
    """
    edge.run("sudo haproxy -c -f /etc/haproxy/haproxy.cfg")
    rechargement = edge.run("sudo systemctl reload haproxy")
    assert rechargement.rc == 0, message(
        en=f"`systemctl reload haproxy` failed: {rechargement.stdout.strip()[:200]!r}",
        fr=f"`systemctl reload haproxy` a échoué : {rechargement.stdout.strip()[:200]!r}",
    )
    time.sleep(3)
    _recette_identite(edge, recette)

    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)

    revenu = _attendre_retour(edge, 180)
    assert revenu, message(
        en="edge.lab did not come back online within 180s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180 s après le redémarrage.",
    )

    # La plateforme de test et HAProxy mettent quelques secondes a revenir.
    limite = time.monotonic() + 180
    pret = False
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
        en=(
            "After the reboot, either HAProxy does not listen on 443 or the test "
            "authority is not answering. The service and the cycle must both "
            "come back by themselves."
        ),
        fr=(
            "Après le redémarrage, soit HAProxy n'écoute pas sur le 443, soit "
            "l'autorité de test ne répond pas. Le service et le cycle doivent "
            "tous deux revenir d'eux-mêmes."
        ),
    )

    _recette_identite(edge, recette)
    _recette_cycle(edge, recette)
