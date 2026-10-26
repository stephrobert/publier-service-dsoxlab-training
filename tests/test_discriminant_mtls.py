"""Le discriminant de `pub-traefik-mtls` sépare-t-il ce que le code HTTP confond ?

POURQUOI CE GARDE-FOU EXISTE

Les tests de `pub-traefik-mtls` ont longtemps conclu sur « un statut
différent de 200 ». Contre-test du 2026-10-25 : ce critère tient **sept
situations sur dix** pour un refus TLS, dont un service éteint, un fichier
de certificat absent et un 404 de routage. Le lab passait donc au vert sans
avoir démontré le moindre refus de certificat.

La correction a été de lire aussi le code de sortie de curl, dans la
fonction `_pourquoi_ce_n_est_pas_un_refus_tls`. Ce fichier est ce qui
empêche de revenir en arrière : il rejoue les dix situations et exige que la
fonction les sépare. Il ne demande aucune machine, puisqu'il ne porte que
sur la décision, qui est l'endroit où le faux positif vivait.

Si quelqu'un remet « différent de 200 », sept de ces dix cas virent au
rouge, et le message dira lesquels.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
SUJET = (
    RACINE / "labs" / "pub-traefik-mtls" / "challenge" / "tests" / "test_functional.py"
)

# (libellé, code HTTP, code de sortie curl, est-ce un vrai refus TLS ?)
SITUATIONS = [
    ("refus TLS, poignée de main rejetée", "000", 35, True),
    ("refus TLS, coupure après la poignée de main", "000", 56, True),
    ("fichier de certificat absent ou illisible", "000", 58, False),
    ("service éteint, connexion refusée", "000", 7, False),
    ("délai dépassé", "000", 28, False),
    ("nom d'hôte introuvable", "000", 6, False),
    ("404 : la route n'existe pas", "404", 0, False),
    ("502 : Traefik a refusé le backend", "502", 0, False),
    ("403 applicatif, la connexion TLS a abouti", "403", 0, False),
    ("certificat accepté", "200", 0, False),
]


def _charger_le_sujet():
    """Importe le test du lab hors de son harnais.

    Il importe `conftest`, qui n'existe que sous `dsoxlab check`. On en pose
    un faux : ce garde-fou ne joue aucune requête, il n'interroge que la
    fonction de décision.
    """
    faux_conftest = types.ModuleType("conftest")
    faux_conftest.lab_host = lambda *a, **k: None
    faux_conftest.lab_target_host = lambda nom: nom
    faux_conftest.message = lambda en, fr: fr
    sys.modules["conftest"] = faux_conftest
    try:
        spec = importlib.util.spec_from_file_location("sujet_mtls", SUJET)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop("conftest", None)


@pytest.fixture(scope="module")
def juge():
    assert SUJET.is_file(), f"{SUJET} est absent : le lab a-t-il été renommé ?"
    module = _charger_le_sujet()
    fonction = getattr(module, "_pourquoi_ce_n_est_pas_un_refus_tls", None)
    assert fonction is not None, (
        "`_pourquoi_ce_n_est_pas_un_refus_tls` a disparu du test du lab. "
        "Si la discrimination a été réécrite ailleurs, ce garde-fou doit "
        "suivre ; si elle a simplement été retirée, le faux positif est de "
        "retour."
    )
    return fonction


@pytest.mark.parametrize(
    ("libelle", "code_http", "code_curl", "vrai_refus"),
    SITUATIONS,
    ids=[s[0] for s in SITUATIONS],
)
def test_chaque_situation_est_classee_pour_ce_qu_elle_est(
    juge, libelle: str, code_http: str, code_curl: int, vrai_refus: bool
) -> None:
    raison = juge(libelle, code_http, code_curl)
    classe_en_refus = raison is None
    if vrai_refus:
        assert classe_en_refus, (
            f"« {libelle} » (HTTP {code_http}, curl {code_curl}) est un vrai "
            f"refus TLS, et il est écarté : {raison}"
        )
    else:
        assert not classe_en_refus, (
            f"« {libelle} » (HTTP {code_http}, curl {code_curl}) est pris pour "
            "un refus TLS alors qu'il n'en est pas un. C'est le faux positif "
            "que ce garde-fou existe pour empêcher."
        )


def test_le_critere_naif_serait_bien_plus_permissif(juge) -> None:
    """La mesure qui justifie tout ce fichier, rejouée à chaque commit.

    On ne se contente pas d'affirmer que l'ancien critère était trop large :
    on le réapplique et on compte. S'il devenait un jour aussi strict que le
    nouveau, ce garde-fou n'aurait plus lieu d'être, et il le dirait.
    """
    laissees_passer = [
        libelle
        for libelle, code, _rc, vrai in SITUATIONS
        if code != "200" and not vrai
    ]
    assert len(laissees_passer) >= 5, (
        "Le jeu de situations ne couvre plus assez de cas pour que la "
        "comparaison ait du sens."
    )
    ecartees = [
        libelle
        for libelle, code, rc, vrai in SITUATIONS
        if code != "200" and not vrai and juge(libelle, code, rc) is not None
    ]
    assert ecartees == laissees_passer, (
        "Le discriminant devrait écarter toutes les situations que le critère "
        "« différent de 200 » laissait passer. Non écartées : "
        f"{sorted(set(laissees_passer) - set(ecartees))}"
    )
