"""Verify the running Nginx matches the manifest, refuses a misplaced
directive without dropping the service, applies a valid change by reload, and
comes back by itself after a reboot.

CE QUE LE SETUP POSE : Nginx installé, le backend en marche, le manifeste
écrit, et RIEN de publié. Le service est arrêté et non activé au démarrage.

LE CONTROLE QUI DECIDE, ET IL EST LE DERNIER

Un service qui répond aujourd'hui et ne revient pas après un redémarrage
n'est pas installé, il est lancé. La différence ne se voit qu'en redémarrant
pour de bon, ce que fait le dernier test. Il est volontairement placé en
dernier : il coupe la machine, et tout ce qui le suivrait mesurerait un
autre état.
"""

from __future__ import annotations

import time

import pytest

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
CLIENT = "poste.lab"
MANIFESTE = "/opt/pub-nginx-installation/manifeste.txt"
NOM = "app.lab.test"
MARQUE = "Nginx installation backend:"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def poste():
    return lab_host(CLIENT)


@pytest.fixture(scope="module")
def ip_edge():
    return lab_host_ip(CIBLE)


def _depuis_le_client(poste, ip: str, chemin: str = "/") -> str:
    return poste.run(
        f"curl -s --max-time 10 -H 'Host: {NOM}' http://{ip}{chemin}"
    ).stdout



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

def test_la_version_et_le_fichier_actif_suivent_le_manifeste(edge, poste, ip_edge) -> None:
    """Ce qui tourne correspond à ce que le manifeste annonce.

    On lit le manifeste au lieu d'écrire une version en dur : un test qui
    affirme « 1.24 » devient faux le jour où la distribution bouge, et
    personne ne saurait dire si c'est le test ou l'installation qui a tort.
    """
    attendu = edge.run(f"grep -oP '(?<=version     : ).*' {MANIFESTE}").stdout.strip()
    assert attendu, message(
        en=f"The manifest {MANIFESTE} does not declare a version.",
        fr=f"Le manifeste {MANIFESTE} ne déclare aucune version.",
    )
    reelle = edge.run("nginx -v 2>&1 | sed 's/.*nginx\\///'").stdout.strip()
    assert reelle == attendu, message(
        en=f"The running Nginx is {reelle!r}, the manifest announces {attendu!r}.",
        fr=f"Le Nginx en service est {reelle!r}, le manifeste annonce {attendu!r}.",
    )

    modules = edge.run("nginx -V 2>&1").stdout
    assert "http_ssl_module" in modules, message(
        en="The running build does not carry http_ssl_module, which the "
        "manifest requires.",
        fr="Le build en service ne porte pas http_ssl_module, que le manifeste "
        "exige.",
    )

    corps = _depuis_le_client(poste, ip_edge)
    assert MARQUE in corps, message(
        en=(
            f"{NOM} does not reach the backend from the client "
            f"(answer: {corps.strip()[:120]!r}). The manifest asks for a site "
            "defined in sites-available and enabled by a symbolic link."
        ),
        fr=(
            f"{NOM} n'atteint pas le backend depuis le client "
            f"(réponse : {corps.strip()[:120]!r}). Le manifeste demande un site "
            "défini dans sites-available et activé par un lien symbolique."
        ),
    )


def test_une_directive_mal_placee_est_refusee_sans_couper_le_service(
    edge, poste, ip_edge
) -> None:
    """La faute est refusée par `nginx -t`, et le service précédent tient.

    LES DEUX MOITIES. Refuser une configuration fautive ne vaut rien si le
    service tombe en même temps : c'est exactement ce que fait un `systemctl
    restart` lancé sans validation préalable. On injecte donc la faute, on
    exige qu'elle soit refusée, ET que le service réponde encore.
    """
    fautif = "/etc/nginx/conf.d/zz-faute-validation.conf"
    # `worker_connections` appartient au contexte `events`, jamais a `http` :
    # la faute est reelle et son message la nomme.
    edge.run(f"printf 'worker_connections 42;\\n' | sudo tee {fautif} >/dev/null")
    try:
        controle = edge.run("sudo nginx -t")
        assert controle.rc != 0, message(
            en=(
                "`nginx -t` accepted a `worker_connections` directive placed in "
                "the http context. Validation that accepts everything proves "
                "nothing about the configuration it validated earlier."
            ),
            fr=(
                "`nginx -t` a accepté une directive `worker_connections` placée "
                "dans le contexte http. Une validation qui accepte tout ne "
                "prouve rien sur la configuration qu'elle a validée avant."
            ),
        )
        corps = _depuis_le_client(poste, ip_edge)
        assert MARQUE in corps, message(
            en=(
                "The service stopped answering while an invalid file merely sat "
                "on disk. A refused configuration must not take the running one "
                "with it: validate before reloading, never after restarting."
            ),
            fr=(
                "Le service a cessé de répondre alors qu'un fichier invalide ne "
                "faisait que traîner sur le disque. Une configuration refusée ne "
                "doit pas emporter celle qui tourne : on valide avant de "
                "recharger, jamais après avoir redémarré."
            ),
        )
    finally:
        edge.run(f"sudo rm -f {fautif}")


def test_un_changement_valide_est_applique_par_reload(edge, poste, ip_edge) -> None:
    """Le changement passe, et le processus maître ne change PAS.

    C'est ce qui distingue un reload d'un restart, et la distinction n'est
    pas théorique : un restart coupe les connexions en cours. On compare donc
    le PID du maître avant et après.
    """
    pid_avant = edge.run("systemctl show -p MainPID --value nginx").stdout.strip()
    assert pid_avant and pid_avant != "0", message(
        en="Nginx is not running: nothing can be reloaded.",
        fr="Nginx ne tourne pas : il n'y a rien à recharger.",
    )

    marqueur = "/etc/nginx/conf.d/zz-temoin-reload.conf"
    edge.run(
        "printf 'server {\\n  listen 18099;\\n  location / "
        "{ return 200 \"temoin-reload\\\\n\"; }\\n}\\n' "
        f"| sudo tee {marqueur} >/dev/null"
    )
    try:
        edge.run("sudo nginx -t && sudo systemctl reload nginx")
        time.sleep(2)

        temoin = edge.run("curl -s --max-time 5 http://127.0.0.1:18099/").stdout
        assert "temoin-reload" in temoin, message(
            en=(
                "A valid change was not applied: the reload did not take place, "
                f"or it failed (answer: {temoin.strip()[:80]!r})."
            ),
            fr=(
                "Un changement valide n'a pas été appliqué : le rechargement n'a "
                f"pas eu lieu, ou il a échoué (réponse : {temoin.strip()[:80]!r})."
            ),
        )

        pid_apres = edge.run("systemctl show -p MainPID --value nginx").stdout.strip()
        assert pid_apres == pid_avant, message(
            en=(
                f"The master process changed ({pid_avant} then {pid_apres}): the "
                "change was applied by a restart, which drops live connections. "
                "A valid change is applied with `systemctl reload`."
            ),
            fr=(
                f"Le processus maître a changé ({pid_avant} puis {pid_apres}) : le "
                "changement a été appliqué par un redémarrage, qui coupe les "
                "connexions en cours. Un changement valide s'applique avec "
                "`systemctl reload`."
            ),
        )
    finally:
        edge.run(f"sudo rm -f {marqueur}")
        edge.run("sudo nginx -t && sudo systemctl reload nginx")


def test_le_service_et_sa_configuration_reviennent_apres_reboot(
    edge, poste, ip_edge
) -> None:
    """CRITIQUE, et dernier : un service lancé n'est pas un service installé.

    Ce test coupe la machine. Il est donc placé en dernier à dessein : tout
    ce qui le suivrait mesurerait un autre état que celui que les tests
    précédents ont établi.
    """
    assert MARQUE in _depuis_le_client(poste, ip_edge), message(
        en="The service must answer before the reboot is attempted.",
        fr="Le service doit répondre avant de tenter le redémarrage.",
    )

    edge.run("nohup bash -c 'sleep 2 && systemctl reboot' >/dev/null 2>&1 &")
    time.sleep(10)

    revenu = _attendre_retour(edge, 180)
    assert revenu, message(
        en="edge.lab did not come back online within 180s after the reboot.",
        fr="edge.lab n'est pas revenu en ligne dans les 180 s après le redémarrage.",
    )

    # Le service peut mettre quelques secondes a reprendre apres le
    # demarrage : on attend, au lieu de conclure sur la premiere tentative.
    corps = ""
    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        corps = _depuis_le_client(poste, ip_edge)
        if MARQUE in corps:
            break
        time.sleep(5)

    assert MARQUE in corps, message(
        en=(
            "After the reboot, the service does not answer again by itself. It "
            "was started, not installed: enable it so systemd brings it back, "
            "and make sure its configuration is on disk rather than applied by "
            "hand."
        ),
        fr=(
            "Après le redémarrage, le service ne répond pas de lui-même. Il "
            "avait été lancé, pas installé : activez-le pour que systemd le "
            "ramène, et vérifiez que sa configuration est sur le disque plutôt "
            "qu'appliquée à la main."
        ),
    )
