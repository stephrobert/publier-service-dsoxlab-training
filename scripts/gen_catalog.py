#!/usr/bin/env python3
"""Génère la table des labs (id, titre, niveau, runtime, guide) dans les README.

Source de vérité : l'ordre des sections de meta.yml, leurs titres français de
meta.fr.yml, et chaque labs/**/lab.yaml (lab.fr.yaml pour le titre français).
Écrit entre les marqueurs <!-- LABS:START --> et <!-- LABS:END --> de
README.md et README.fr.md.

LES LIENS SONT CALCULÉS, JAMAIS ÉCRITS À LA MAIN. Le `doc_url` d'un lab est la
leçon française, parce que la CLI dsoxlab le lit aussi. Le README anglais pointe
vers la traduction quand elle existe, lue dans scripts/doc_url_en.json, que
scripts/gen_doc_url_en.py produit depuis les `translationOf` du site ; sinon il
garde le guide français, marqué « (FR) ».

Usage :
    python3 scripts/gen_catalog.py           # régénère les README
    python3 scripts/gen_catalog.py --check    # échoue (exit 1) si un README est périmé
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Un seul chemin de lecture pour tout le catalogue : voir scripts/lecture_yaml.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lecture_yaml import YamlIllisible, lire_yaml

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "meta.yml"
META_FR = ROOT / "meta.fr.yml"
DOC_URL_EN = ROOT / "scripts" / "doc_url_en.json"
START, END = "<!-- LABS:START -->", "<!-- LABS:END -->"

HEAD = {
    "en": ("Lab (id)", "Title", "Level", "Runtime", "Companion guide"),
    "fr": ("Lab (id)", "Titre", "Niveau", "Runtime", "Guide compagnon"),
}


def _titres_sections_fr() -> dict[str, str]:
    """Titres français des sections, appariés par `id`, jamais par position."""
    if not META_FR.exists():
        return {}
    try:
        meta_fr = lire_yaml(META_FR)
    except YamlIllisible as exc:
        print(f"  titres français ignorés : {exc}", file=sys.stderr)
        return {}
    return {s.get("id", ""): s.get("title", "") for s in meta_fr.get("sections") or []}


def _descriptions_sections_fr() -> dict[str, str]:
    """Descriptions françaises des sections, appariées par `id`, pas par position."""
    if not META_FR.exists():
        return {}
    try:
        meta_fr = lire_yaml(META_FR)
    except YamlIllisible as exc:
        print(f"  descriptions françaises ignorées : {exc}", file=sys.stderr)
        return {}
    return {
        s.get("id", ""): s.get("description", "")
        for s in meta_fr.get("sections") or []
    }


def _sections() -> list[tuple[str, dict[str, str], dict[str, str], list[dict]]]:
    """[(id, titres, descriptions, labs), ...] dans l'ordre de meta.yml."""
    try:
        meta = lire_yaml(META)
    except YamlIllisible as exc:
        sys.exit(f"catalogue ingénérable : {exc}")
    titres_fr = _titres_sections_fr()
    descriptions_fr = _descriptions_sections_fr()
    out = []
    for section in meta.get("sections", []):
        labs: list[dict] = []
        for rel in section.get("labs") or []:
            lab_dir = ROOT / "labs" / rel
            lab_yaml = lab_dir / "lab.yaml"
            if not lab_yaml.exists():
                continue
            try:
                lab = lire_yaml(lab_yaml)
            except YamlIllisible as exc:
                print(f"  lab écarté du catalogue : {rel}/{exc}", file=sys.stderr)
                continue
            lab["_title_fr"] = lab.get("title", "")
            fr_yaml = lab_dir / "lab.fr.yaml"
            if fr_yaml.exists():
                try:
                    lab["_title_fr"] = lire_yaml(fr_yaml).get("title", lab["_title_fr"])
                except YamlIllisible as exc:
                    print(f"  {rel}/{exc}", file=sys.stderr)
            labs.append(lab)
        if labs:
            sid = section.get("id", "")
            titres = {
                "en": section.get("title", ""),
                "fr": titres_fr.get(sid) or section.get("title", ""),
            }
            # La description dit ce que la section fait travailler. Elle vit
            # dans `meta.yml`, et c'est la seule source : avant que le
            # catalogue soit généré, elle était recopiée dans le README, où
            # elle se périmait sans que rien ne le dise.
            descriptions = {
                "en": section.get("description", ""),
                "fr": descriptions_fr.get(sid) or section.get("description", ""),
            }
            out.append((sid, titres, descriptions, labs))
    return out


def _doc_url_en() -> dict[str, str]:
    if not DOC_URL_EN.exists():
        return {}
    return json.loads(DOC_URL_EN.read_text(encoding="utf-8"))


def _guide(lab: dict, lang: str) -> str:
    url = lab.get("doc_url", "")
    if not url:
        return "-"
    if lang == "en":
        en = _doc_url_en().get(url)
        return f"[guide]({en})" if en else f"[guide (FR)]({url})"
    return f"[guide]({url})"


def _table(lang: str) -> str:
    entetes = HEAD[lang]
    lignes: list[str] = []
    sections = _sections()
    for _sid, titres, descriptions, labs in sections:
        lignes += [f"### {titres[lang]}", ""]
        if descriptions[lang]:
            lignes += [descriptions[lang], ""]
        lignes += ["| " + " | ".join(entetes) + " |",
                   "|" + "|".join(["---"] * len(entetes)) + "|"]
        for lab in labs:
            titre = lab["_title_fr"] if lang == "fr" else lab.get("title", "")
            runtime = str((lab.get("runtime") or {}).get("type", "shell"))
            lignes.append(f"| `{lab.get('id', '')}` | {titre} | {lab.get('level', '')} | {runtime} | {_guide(lab, lang)} |")
        lignes.append("")
    total = sum(len(labs) for _s, _t, _d, labs in sections)
    lignes.append(
        f"_{total} labs, table generated by `scripts/gen_catalog.py`._"
        if lang == "en"
        else f"_{total} labs, table générée par `scripts/gen_catalog.py`._"
    )
    return "\n".join(lignes)


def _rendu(chemin: Path, bloc: str) -> str:
    texte = chemin.read_text(encoding="utf-8")
    if START not in texte or END not in texte:
        raise SystemExit(f"marqueurs absents dans {chemin}")
    return f"{texte.split(START)[0]}{START}\n{bloc}\n{END}{texte.split(END)[1]}"


CIBLES = {"README.md": "en", "README.fr.md": "fr"}


def _verifier() -> int:
    perimes = [n for n, lang in CIBLES.items()
               if (ROOT / n).read_text(encoding="utf-8") != _rendu(ROOT / n, _table(lang))]
    if perimes:
        print("Catalogue périmé dans : " + ", ".join(perimes)
              + "\nLance `python3 scripts/gen_catalog.py` puis recommite.", file=sys.stderr)
        return 1
    print("catalogue à jour")
    return 0


def _ecrire() -> None:
    for nom, lang in CIBLES.items():
        chemin = ROOT / nom
        chemin.write_text(_rendu(chemin, _table(lang)), encoding="utf-8")
    print("catalogue régénéré dans README.md et README.fr.md")


def main() -> None:
    if "--check" in sys.argv[1:]:
        raise SystemExit(_verifier())
    _ecrire()


if __name__ == "__main__":
    main()
