"""Verify security headers, authentication, dotfile denial, and method policy."""

from __future__ import annotations

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
URL = "http://app.lab.test"
RESOLUTION = "--resolve app.lab.test:80:127.0.0.1"


def test_entetes_de_securite_sont_presentes() -> None:
    result = lab_host(CIBLE).run(
        f"curl --max-time 5 --silent --show-error --dump-header - "
        f"--output /dev/null {RESOLUTION} {URL}/health"
    )
    required = (
        "X-Content-Type-Options: nosniff",
        "X-Frame-Options: DENY",
        "Referrer-Policy: no-referrer",
        "Content-Security-Policy: default-src 'self'; frame-ancestors 'none'",
    )
    missing = [header for header in required if header.lower() not in result.stdout.lower()]
    assert result.rc == 0 and not missing, message(
        en=f"Required security headers are missing: {missing}.",
        fr=f"En-têtes de sécurité manquants : {missing}.",
    )


def test_admin_exige_une_authentification_valide() -> None:
    edge = lab_host(CIBLE)
    anonymous = edge.run(
        f"curl --max-time 5 --silent --show-error --output /dev/null "
        f"--write-out '%{{http_code}}' {RESOLUTION} {URL}/admin"
    )
    authenticated = edge.run(
        f"curl --max-time 5 --silent --show-error --user "
        f"labadmin:Lab-Admin-Only {RESOLUTION} {URL}/admin"
    )
    assert (
        anonymous.rc == 0
        and anonymous.stdout.strip() == "401"
        and authenticated.rc == 0
        and "Nginx protection backend: /admin" in authenticated.stdout
    ), message(
        en="The admin route must challenge anonymous users and serve the "
        "backend to a user authenticated with the supplied credentials.",
        fr="La route d'administration doit refuser les utilisateurs anonymes "
        "et publier le backend pour un utilisateur authentifié avec les "
        "identifiants fournis.",
    )


def test_fichiers_caches_sont_refuses() -> None:
    result = lab_host(CIBLE).run(
        f"curl --max-time 5 --silent --show-error --output /dev/null "
        f"--write-out '%{{http_code}}' {RESOLUTION} {URL}/.env"
    )
    assert result.rc == 0 and result.stdout.strip() in {"403", "404"}, message(
        en=f"The hidden .env file must be denied, not served "
        f"(HTTP {result.stdout.strip() or 'no response'}).",
        fr=f"Le fichier caché .env doit être refusé, pas publié "
        f"(HTTP {result.stdout.strip() or 'aucune réponse'}).",
    )


def test_methode_delete_est_refusee() -> None:
    result = lab_host(CIBLE).run(
        f"curl --max-time 5 --silent --show-error --request DELETE "
        f"--output /dev/null --write-out '%{{http_code}}' "
        f"{RESOLUTION} {URL}/health"
    )
    assert result.rc == 0 and result.stdout.strip() in {"403", "405"}, message(
        en=f"DELETE must be rejected (HTTP {result.stdout.strip() or 'no response'}).",
        fr=f"DELETE doit être refusée (HTTP {result.stdout.strip() or 'aucune réponse'}).",
    )
