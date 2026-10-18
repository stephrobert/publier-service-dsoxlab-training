# Contribuer

## La règle unique

**Un lab est noté sur l'état du système, jamais sur les commandes tapées.**

Un test qui relit ce que l'apprenant a écrit ne prouve rien : il a pu l'écrire
sans le comprendre, et il a pu atteindre le même état par un autre chemin que
le test rejetterait à tort.

```python
# NON : on relit ce que l'apprenant a écrit
assert "monoption" in texte_de_config

# OUI : on demande au système ce qu'il fait vraiment
assert service.is_running and service.is_enabled
```

## Un lab est prouvé dans les deux sens

Avant qu'un lab soit fusionné :

1. `dsoxlab run <id>` puis `dsoxlab check <id>` doivent rendre **0**. Un test
   vert avant le travail n'est pas un test, c'est une hypothèse sur le setup.
2. La solution de référence posée, `dsoxlab check <id>` doit rendre **100**.
3. `dsoxlab clean <id>` doit rendre la machine telle qu'elle était. Un lab qui
   laisse quelque chose derrière lui n'embête pas ce lab-là, il embête le
   suivant.

## Tout ce qui s'affiche est bilingue

L'énoncé existe en anglais et en français : `README.md` et `README.fr.md`,
`scenario.md` et `scenario.fr.md`, `lab.yaml` et `lab.fr.yaml`.

Les messages d'assertion sont un cas à part : le contrat impose un nom de
fichier unique, `challenge/tests/test_functional.py`, donc il n'y a pas de
version anglaise par duplication. Emploie le helper `message(en=…, fr=…)` de
`conftest.py`.

## Avant d'ouvrir une demande de fusion

```bash
dsoxlab validate-structure     # le contrat, hors ligne
pytest tests/                  # les garde-fous propres à ce dépôt
dsoxlab list-labs              # D'ABORD : un lab.yaml qui lève disparaît ici
```

Joue `list-labs` **avant** `validate-structure` : le validateur itère sur les
labs déjà chargés, donc un lab dont le `lab.yaml` lève passe la validation sans
un mot.
