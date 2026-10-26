#!/usr/bin/env python3
"""Les tests des labs ont-ils tout ce dont ils ont besoin pour tourner ?

POURQUOI CE CONTROLE EXISTE, ET POURQUOI `--collect-only` NE SUFFIT PAS

Le 2026-10-22, le test du cache du lab 12 a echoue sur

    NameError: name 're' is not defined

apres une reecriture ou l'import avait ete oublie. Or `pytest --collect-only`
avait rendu « 2 tests collected » sans broncher : la collecte IMPORTE le
module, elle n'execute pas les corps de fonctions. Un nom manquant dans un
corps passe donc la collecte et casse a l'appel, c'est-a-dire pendant le cycle
de validation, dix minutes plus tard, sur une VM.

C'est exactement l'ecart que la doctrine du depot resume ainsi : « le controle
doit porter sur le comportement, pas sur la forme ». `ast.parse` et la collecte
pytest valident la forme ; ce controle-ci cherche les NOMS qu'aucun import ni
aucune affectation ne fournit.

Il ne remplace pas le cycle de validation : il le fait echouer plus tot, et
pour trois centiemes de seconde.

Usage :

    python3 scripts/check-tests.py          # tous les tests des labs
    python3 scripts/check-tests.py <f> ...  # ceux qu'on nomme
"""

from __future__ import annotations

import ast
import builtins
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

# Les noms que pytest, le conftest et l'usage fournissent sans import visible.
TOLERES = {"__file__", "__name__", "__doc__", "_", "pytest"}


def fichiers() -> list[Path]:
    return sorted(RACINE.glob("labs/*/challenge/tests/test_*.py"))


def noms_fournis(arbre: ast.Module) -> set[str]:
    """Tout ce que le module definit lui-meme : imports, variables, fonctions."""
    fournis: set[str] = set(dir(builtins)) | TOLERES
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                fournis.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                fournis.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fournis.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            fournis.add(n.id)
        elif isinstance(n, ast.arg):
            fournis.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            fournis.add(n.name)
        elif isinstance(n, (ast.comprehension,)):
            pass
    return fournis


def noms_utilises(arbre: ast.Module) -> list[tuple[str, int]]:
    return [
        (n.id, n.lineno)
        for n in ast.walk(arbre)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    ]


def controle(fichier: Path) -> list[str]:
    try:
        arbre = ast.parse(fichier.read_text(), filename=str(fichier))
    except SyntaxError as e:
        return [f"syntaxe refusee ligne {e.lineno} : {e.msg}"]

    fournis = noms_fournis(arbre)
    manquants: dict[str, int] = {}
    for nom, ligne in noms_utilises(arbre):
        if nom not in fournis and nom not in manquants:
            manquants[nom] = ligne
    return [
        f"ligne {ligne} : « {nom} » n'est ni importe ni defini"
        for nom, ligne in sorted(manquants.items(), key=lambda x: x[1])
    ]


def main() -> int:
    cibles = [Path(a).resolve() for a in sys.argv[1:]] or fichiers()
    if not cibles:
        print("aucun fichier de tests trouve")
        return 0

    # Un linter complet, s'il est installe, voit bien plus que ce controle :
    # on le lance d'abord, et on ne le rend pas obligatoire.
    ruff = subprocess.run(["which", "ruff"], check=False, capture_output=True, text=True)
    if ruff.returncode == 0:
        r = subprocess.run(
            ["ruff", "check", "--select", "F", *[str(c) for c in cibles]],
            cwd=RACINE, check=False, capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(r.stdout.strip() or r.stderr.strip())
            print("\nruff refuse ces fichiers.")
            return 1

    echecs = 0
    for f in cibles:
        ecarts = controle(f)
        rel = f.relative_to(RACINE) if RACINE in f.parents else f
        if ecarts:
            echecs += 1
            print(f"  REFUSE {rel}")
            for e in ecarts:
                print(f"      {e}")
        else:
            print(f"  ok     {rel}")

    print()
    if echecs:
        print(f"{echecs} fichier(s) de tests ne tourneraient pas.")
        print("Rappel : `pytest --collect-only` ne le voit pas, la collecte")
        print("important le module sans executer les corps de fonctions.")
        return 1
    print(f"{len(cibles)} fichier(s) de tests ont tous leurs noms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
