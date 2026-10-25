#!/usr/bin/env python3
"""Navigateur automatisable fourni pour le lab pub-socle-application.

Ceci n'est pas un outil que l'apprenant écrit ou corrige : c'est
l'instrument d'observation, déjà installé par `prepare.sh` sur edge.lab,
qui permet de regarder les quatre points testés (parcours de connexion,
session, origines, identité) depuis l'endroit où ils comptent réellement,
un vrai moteur de navigateur, pas seulement les en-têtes vus par curl.

Usage ::

    python3 verifier_navigateur.py parcours <port_entree>
    python3 verifier_navigateur.py cors <port_partenaire> <port_intrus>
    python3 verifier_navigateur.py identite <port_entree>

Chaque sous-commande imprime un objet JSON sur stdout.
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/ms-playwright")

from playwright.sync_api import sync_playwright  # noqa: E402


def _parcours(port_entree: str) -> dict:
    resultat = {
        "connexion_ok": False,
        "url_finale": None,
        "schema_final": None,
        "compte_affiche": None,
        "erreur": None,
    }
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        contexte = navigateur.new_context(ignore_https_errors=True)
        page = contexte.new_page()
        try:
            page.goto(f"https://127.0.0.1:{port_entree}/login", timeout=8000)
            with page.expect_navigation(wait_until="load", timeout=8000):
                page.click("button[type=submit]")
            resultat["url_finale"] = page.url
            resultat["schema_final"] = page.url.split(":", 1)[0]
            resultat["connexion_ok"] = "/compte" in page.url
            texte = page.inner_text("body")
            resultat["compte_affiche"] = "connecte" in texte and "anonyme" not in texte
        except Exception as erreur:  # navigation trop de redirections, etc.
            resultat["erreur"] = str(erreur)
        finally:
            navigateur.close()
    return resultat


def _cors(port_partenaire: str, port_intrus: str) -> dict:
    resultat = {"partenaire": None, "intrus": None}
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        contexte = navigateur.new_context(ignore_https_errors=True)
        for nom, port in (("partenaire", port_partenaire), ("intrus", port_intrus)):
            page = contexte.new_page()
            page.goto(f"http://127.0.0.1:{port}/", timeout=8000)
            page.wait_for_function(
                "document.getElementById('resultat').innerText !== 'en-cours'",
                timeout=8000,
            )
            contenu = page.inner_text("#resultat")
            try:
                resultat[nom] = json.loads(contenu)
            except json.JSONDecodeError:
                resultat[nom] = {"ok": False, "erreur": contenu}
            page.close()
        navigateur.close()
    return resultat


def _identite(port_entree: str) -> dict:
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        contexte = navigateur.new_context(ignore_https_errors=True)
        page = contexte.new_page()
        # Aucune connexion préalable : aucun cookie de session légitime.
        page.goto(f"https://127.0.0.1:{port_entree}/login", timeout=8000)
        reponse = page.evaluate(
            """async (port) => {
                const r = await fetch(`https://127.0.0.1:${port}/api/identite`, {
                    headers: {"X-Pub-User": "etudiant"},
                });
                return {statut: r.status, corps: await r.text()};
            }""",
            port_entree,
        )
        navigateur.close()
    try:
        identite = json.loads(reponse["corps"]).get("identite")
    except json.JSONDecodeError:
        identite = None
    return {
        "identite_reconnue": identite == "etudiant",
        "corps": reponse["corps"],
        "statut": reponse["statut"],
    }


def principal() -> None:
    commande = sys.argv[1]
    if commande == "parcours":
        sortie = _parcours(sys.argv[2])
    elif commande == "cors":
        sortie = _cors(sys.argv[2], sys.argv[3])
    elif commande == "identite":
        sortie = _identite(sys.argv[2])
    else:
        raise SystemExit(f"commande inconnue: {commande}")
    print(json.dumps(sortie))


if __name__ == "__main__":
    principal()
