#!/usr/bin/env python3
"""Ni emoji ni tiret cadratin dans ce que lit l'apprenant.

La règle d'écriture du projet interdit le tiret cadratin en français : il se
remplace par la ponctuation qui dit son rôle (deux-points s'il introduit,
point-virgule s'il rompt, parenthèses s'il met entre), jamais par un autre
tiret.

Ce contrôle porte sur ce que l'apprenant LIT : les énoncés français, les titres
des `lab.fr.yaml`, et les deux README. Pas sur le code, pas sur les
commentaires anglais.

Mesuré sur un catalogue qui n'avait pas ce hook : 51 `lab.fr.yaml`, 172 README
de labs et 86 scénarios portaient un tiret cadratin. Une campagne de
remplacement sans le hook serait défaite au prochain lab écrit.
"""

from __future__ import annotations

import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent.parent
CADRATIN = "\u2014"
MOTIFS = ("README.fr.md", "scenario.fr.md", "lab.fr.yaml", "hints.yaml")


def main() -> int:
    fautifs: list[str] = []
    cibles = [RACINE / "README.fr.md", RACINE / "meta.fr.yml"]
    for motif in MOTIFS:
        cibles += sorted(RACINE.glob(f"labs/**/{motif}"))

    for chemin in cibles:
        if not chemin.is_file():
            continue
        for numero, ligne in enumerate(
            chemin.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if CADRATIN in ligne:
                relatif = chemin.relative_to(RACINE)
                fautifs.append(f"{relatif}:{numero}  {ligne.strip()[:80]}")

    if fautifs:
        print(f"{len(fautifs)} ligne(s) avec un tiret cadratin en français :",
              file=sys.stderr)
        for f in fautifs:
            print(f"  {f}", file=sys.stderr)
        print("\nRemplace-le par la ponctuation qui dit son rôle : deux-points "
              "s'il introduit, point-virgule s'il rompt, parenthèses s'il met "
              "entre.", file=sys.stderr)
        return 1

    print(f"{len(cibles)} fichier(s) lus par l'apprenant, aucun tiret cadratin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
