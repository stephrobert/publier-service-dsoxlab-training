"""Vérifie les rôles réels de la chaîne de proxys, que l'origine et
l'identité d'un client légitime sont préservées, et qu'aucune des deux ne
peut encore être forgée depuis le client une fois la chaîne corrigée.

Les tests sondent eux-mêmes la chaîne, depuis poste.lab et edge.lab, avec
l'autorité de test fournie et sans jamais désactiver la vérification TLS
(sauf la sonde interne qui confirme qu'un hop ne parle pas TLS du tout).
Rien ici ne fait confiance au texte de la fiche de l'apprenant sans le
confronter à ce qui est réellement observé.
"""

from __future__ import annotations

import json

import pytest
import yaml

from conftest import lab_host, lab_host_ip, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
FICHE = "/home/student/diagnostic.yaml"
ETAT = "/var/lib/pub-rp/etat.json"
CA = "/home/student/ca.pem"
CA_EDGE = "/etc/pub-rp/certs/ca.pem"


@pytest.fixture(scope="module")
def edge():
    return lab_host(CIBLE)


@pytest.fixture(scope="module")
def client():
    return lab_host("poste.lab")


@pytest.fixture(scope="module")
def etat(edge):
    return json.loads(edge.run(f"sudo cat {ETAT}").stdout)


@pytest.fixture(scope="module")
def fiche(edge):
    fichier = edge.file(FICHE)
    assert fichier.exists, message(
        en=f"{FICHE} does not exist on edge.lab.",
        fr=f"{FICHE} n'existe pas sur edge.lab.",
    )
    try:
        contenu = yaml.safe_load(fichier.content_string)
    except yaml.YAMLError as erreur:
        pytest.fail(
            message(
                en=f"{FICHE} is not valid YAML: {erreur}",
                fr=f"{FICHE} n'est pas un YAML valide : {erreur}",
            )
        )
    assert isinstance(contenu, dict), message(
        en=f"{FICHE} must contain a YAML mapping.",
        fr=f"{FICHE} doit contenir un dictionnaire YAML.",
    )
    return contenu


def _code(hote, url: str, cacert: str | None = None, resolve: str | None = None, entetes: dict | None = None) -> str:
    opts = [f"--cacert {cacert}" if cacert else "-k"]
    if resolve:
        opts.append(f"--resolve {resolve}")
    for cle, valeur in (entetes or {}).items():
        opts.append(f"-H '{cle}: {valeur}'")
    cmd = "curl -s --max-time 3 " + " ".join(opts) + f" -o /dev/null -w '%{{http_code}}' {url}"
    return hote.run(cmd).stdout.strip()


def _json(hote, url: str, cacert: str, resolve: str, entetes: dict | None = None) -> dict:
    opts = [f"--cacert {cacert}", f"--resolve {resolve}"]
    for cle, valeur in (entetes or {}).items():
        opts.append(f"-H '{cle}: {valeur}'")
    cmd = "curl -s --max-time 5 " + " ".join(opts) + f" {url}"
    res = hote.run(cmd)
    assert res.rc == 0, message(
        en=f"TLS request to the perimetre hop failed (rc={res.rc}).",
        fr=f"La requête TLS vers le maillon périmètre a échoué (rc={res.rc}).",
    )
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            message(
                en=f"The application did not answer JSON: {res.stdout!r}",
                fr=f"L'application n'a pas répondu en JSON : {res.stdout!r}",
            )
        )


def test_roles_tls_et_ports_correspondent_au_trafic(edge, etat, fiche) -> None:
    for champ, attendu in (
        ("perimetre_tls", True),
        ("interne_tls", False),
        ("backend_tls", False),
    ):
        assert fiche.get(champ) == attendu, message(
            en=f"'{champ}' must be {attendu}.",
            fr=f"'{champ}' doit valoir {attendu}.",
        )

    nom = etat["nom_tls"]
    perimetre, interne, backend = etat["perimetre_port"], etat["interne_port"], etat["backend_port"]

    code_tls = _code(edge, f"https://{nom}:{perimetre}/", cacert=CA_EDGE, resolve=f"{nom}:{perimetre}:127.0.0.1")
    assert code_tls == "200", message(
        en="The perimetre hop must answer in TLS with the test authority.",
        fr="Le maillon périmètre doit répondre en TLS avec l'autorité de test.",
    )
    code_plain_sur_perimetre = _code(edge, f"http://127.0.0.1:{perimetre}/")
    assert code_plain_sur_perimetre != "200", message(
        en="The perimetre hop must not answer plain HTTP: it only speaks TLS.",
        fr="Le maillon périmètre ne doit pas répondre en HTTP clair : il ne parle que TLS.",
    )

    for nom_hop, port in (("interne", interne), ("backend", backend)):
        code_plain = _code(edge, f"http://127.0.0.1:{port}/")
        assert code_plain == "200", message(
            en=f"The {nom_hop} hop must answer in plain HTTP on edge.lab's loopback.",
            fr=f"Le maillon {nom_hop} doit répondre en HTTP clair sur la boucle locale de edge.lab.",
        )
        code_tls_sur_hop = _code(edge, f"https://127.0.0.1:{port}/")
        assert code_tls_sur_hop != "200", message(
            en=f"The {nom_hop} hop must not terminate TLS: it only relays in plain HTTP.",
            fr=f"Le maillon {nom_hop} ne doit pas terminer TLS : il ne relaie qu'en HTTP clair.",
        )


def test_origine_et_identite_legitimes_preservees(client, etat, fiche) -> None:
    for champ in ("origine_forcee_par_perimetre", "identite_forcee_par_interne"):
        assert fiche.get(champ) is True, message(
            en=f"'{champ}' must be true.",
            fr=f"'{champ}' doit valoir true.",
        )

    nom, port, ip_edge = etat["nom_tls"], etat["perimetre_port"], etat["edge_ip"]
    ip_client = lab_host_ip("poste.lab")
    corps = _json(client, f"https://{nom}:{port}/", cacert=CA, resolve=f"{nom}:{port}:{ip_edge}")

    assert corps.get("ip_retenue") == ip_client, message(
        en=f"A legitimate request must keep {ip_client} as the retained origin, got {corps.get('ip_retenue')!r}.",
        fr=f"Une requête légitime doit conserver {ip_client} comme origine retenue, reçu {corps.get('ip_retenue')!r}.",
    )
    assert corps.get("identite_retenue") == "anonyme", message(
        en=f"A legitimate request must keep 'anonyme' as the retained identity, got {corps.get('identite_retenue')!r}.",
        fr=f"Une requête légitime doit conserver 'anonyme' comme identité retenue, reçu {corps.get('identite_retenue')!r}.",
    )


def test_usurpation_xff_et_identite_sans_privilege(client, etat, fiche) -> None:
    """Point critique : un en-tête forgé par le client ne doit accorder
    aucun privilège une fois la chaîne corrigée."""
    assert fiche.get("usurpation_sans_privilege") is True, message(
        en="'usurpation_sans_privilege' must be true.",
        fr="'usurpation_sans_privilege' doit valoir true.",
    )

    nom, port, ip_edge = etat["nom_tls"], etat["perimetre_port"], etat["edge_ip"]
    ip_client = lab_host_ip("poste.lab")
    origine_forgee = etat["origine_forgee"]
    corps = _json(
        client,
        f"https://{nom}:{port}/",
        cacert=CA,
        resolve=f"{nom}:{port}:{ip_edge}",
        entetes={"X-Forwarded-For": origine_forgee, "X-User": "admin"},
    )

    assert corps.get("ip_retenue") != origine_forgee, message(
        en=(
            f"A forged X-Forwarded-For ({origine_forgee}) was retained as the "
            "origin: the perimetre hop must decide the origin itself, not "
            "repeat what the client sent."
        ),
        fr=(
            f"Un X-Forwarded-For forgé ({origine_forgee}) a été retenu comme "
            "origine : le maillon périmètre doit décider lui-même l'origine, "
            "pas reconduire ce qu'a envoyé le client."
        ),
    )
    assert corps.get("ip_retenue") == ip_client, message(
        en=f"The retained origin must be the client's real address ({ip_client}), got {corps.get('ip_retenue')!r}.",
        fr=f"L'origine retenue doit être l'adresse réelle du client ({ip_client}), reçu {corps.get('ip_retenue')!r}.",
    )
    assert corps.get("identite_retenue") != "admin", message(
        en="A forged X-User: admin was retained: the interne hop must decide the identity itself.",
        fr="Un X-User: admin forgé a été retenu : le maillon interne doit décider lui-même l'identité.",
    )
    assert "secret" not in corps, message(
        en="The forged identity reached reserved data.",
        fr="L'identité forgée a atteint une donnée réservée.",
    )


def test_contournement_ferme_depuis_le_client(client, etat, fiche) -> None:
    """Point critique : ni le maillon interne ni le backend ne doivent être
    joignables directement depuis le client, même avec un en-tête forgé."""
    assert fiche.get("contournement_ferme") is True, message(
        en="'contournement_ferme' must be true.",
        fr="'contournement_ferme' doit valoir true.",
    )

    ip_edge = etat["edge_ip"]
    for nom_hop, port in (("interne", etat["interne_port"]), ("backend", etat["backend_port"])):
        code = _code(
            client,
            f"http://{ip_edge}:{port}/",
            entetes={"X-User": "admin", "X-Forwarded-For": "10.0.0.1"},
        )
        assert code in ("", "000"), message(
            en=(
                f"The {nom_hop} hop is still directly reachable from the "
                f"client, bypassing the perimetre (http_code={code!r})."
            ),
            fr=(
                f"Le maillon {nom_hop} reste joignable directement depuis le "
                f"client, en contournant le périmètre (http_code={code!r})."
            ),
        )
