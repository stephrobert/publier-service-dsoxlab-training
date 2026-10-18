"""Le catalogue tient ses propres promesses, et pas seulement le contrat.

`dsoxlab validate-structure` vérifie le CONTRAT. Ces tests vérifient ce que ce
dépôt-ci promet en plus, et que l'outil ne peut pas connaître.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _labs() -> list[pathlib.Path]:
    return sorted(RACINE.glob("labs/**/lab.yaml"))


def test_aucun_lab_na_disparu_en_silence() -> None:
    """Un répertoire de lab sans `lab.yaml` lisible est un défaut muet.

    `validate-structure` itère sur ce qui a CHARGÉ : un `lab.yaml` qui lève au
    parsing disparaît du catalogue en silence, et la validation passe sans un
    mot. Ce test est le seul qui attrape ce cas.

    Deux situations que « zéro lab » confond, et qu'on sépare donc :

        labs/ vide                   un catalogue neuf, rien à conclure
        labs/ peuplé, aucun lab.yaml un défaut, et on le nomme
    """
    repertoires = [
        chemin
        for chemin in (RACINE / "labs").rglob("*")
        if chemin.is_dir() and not chemin.name.startswith(".")
    ]
    if not repertoires:
        pytest.skip(
            "labs/ est vide : catalogue neuf, crée un lab avec "
            "`dsoxlab new lab <id>`"
        )

    assert _labs(), (
        f"{len(repertoires)} répertoire(s) sous labs/ mais aucun lab.yaml "
        "lisible : un lab.yaml lève au parsing et a disparu du catalogue en "
        "silence. Joue `dsoxlab list-labs` pour le voir."
    )


def test_chaque_lab_est_declare_dans_le_meta() -> None:
    """Un lab présent sur le disque mais absent du meta.yml n'est pas ordonné.

    Il reste jouable, mais il n'apparaît dans aucune section : ni `list-labs`
    ni `next` ne savent où le placer.
    """
    meta = yaml.safe_load((RACINE / "meta.yml").read_text(encoding="utf-8"))
    declares = {
        chemin
        for section in (meta.get("sections") or [])
        for chemin in (section.get("labs") or [])
    }
    sur_le_disque = {
        p.parent.relative_to(RACINE / "labs").as_posix() for p in _labs()
    }
    orphelins = sorted(sur_le_disque - declares)

    assert not orphelins, (
        f"{len(orphelins)} lab(s) sur le disque mais absents des sections du "
        f"meta.yml : {orphelins}"
    )


def test_le_meta_ne_declare_pas_de_lab_absent() -> None:
    """L'inverse, que `validate-structure` ne vérifie pas.

    Le validateur itère sur `discover_labs()`, donc sur ce qui existe : un lab
    déclaré dans le meta.yml mais absent du disque passe sans un mot.
    """
    meta = yaml.safe_load((RACINE / "meta.yml").read_text(encoding="utf-8"))
    declares = {
        chemin
        for section in (meta.get("sections") or [])
        for chemin in (section.get("labs") or [])
    }
    manquants = sorted(
        c for c in declares if not (RACINE / "labs" / c / "lab.yaml").is_file()
    )

    assert not manquants, (
        f"{len(manquants)} lab(s) déclarés dans le meta.yml mais absents du "
        f"disque : {manquants}"
    )


def test_parite_des_langues() -> None:
    """Un énoncé traduit d'un seul côté est signalé, pas laissé à la relecture."""
    boiteux = []
    for lab in _labs():
        base = lab.parent
        for nom in ("README", "scenario"):
            en = base / f"{nom}.md"
            fr = base / f"{nom}.fr.md"
            if en.is_file() != fr.is_file():
                boiteux.append(f"{base.name}/{nom}")

    assert not boiteux, f"traduits d'un seul côté : {boiteux}"
