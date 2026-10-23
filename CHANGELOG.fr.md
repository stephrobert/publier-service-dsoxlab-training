# Journal des modifications

Les changements notables de ce catalogue sont consignés ici. Le format suit
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et ce catalogue suit
le [versionnage sémantique](https://semver.org/lang/fr/).

**Ce qu'une version veut dire ici.** Un catalogue n'est pas une bibliothèque :
un incrément MINEUR ajoute des labs, un CORRECTIF corrige un énoncé ou un test
sans changer ce qu'un lab prouve, et un incrément MAJEUR renomme ou retire des
labs, ce qui casse la progression déjà enregistrée des apprenants.

## [0.1.0] - 2026-10-23

### Ajouté

- **Première publication.** Deux labs pour publier des services derrière un
  reverse proxy avec des certificats automatiques, 1 h 10 en tout, sur une
  machine Ubuntu 24.04.

- Les deux corrigés de référence sont chiffrés par `ansible-vault`.

- **La chaîne de contribution des catalogues frères** : Zizmor, Actionlint,
  Poutine, parité pre-commit et CodeQL sur `python` et `actions`, plus
  Plumber, Scorecard, Dependabot et les gabarits d'issue. La CI passe d'un job
  à **six**, pour sept contrôles requis, et `main` porte le même ruleset que
  les autres : historique linéaire, pull request avec une revue, et les sept
  contrôles.

- Le hook qui refuse un verdict commité avec ce qu'il mesure, et le jeu de
  règles `ruff` commun à la collection.

### Corrigé

- Le `doc_url` de `pub-01-acme-pebble` pointait
  `/docs/services/web/certificats-acme/`, qui rend **404** : cette page
  n'existe pas, et le README du lab annonçait encore un guide « en cours
  d'écriture ». Il pointe désormais
  `/docs/services/reseau/traefik-tls-acme/`, qui rend 200 et traite le sujet.
  Une première tentative visait le pivot de la section, ce qui était une erreur
  de règle : un lab se rattache à la page qui couvre la compétence, jamais à un
  pivot.

### Manques connus

- `pub-02-traefik-docker` porte un verdict **ROUGE** : le corrigé de référence
  ne passe que 5 tests sur 6. Soit il est faux, soit un test exige
  l'impossible. C'est inscrit en ROUGE plutôt que caché, et c'est la prochaine
  chose à trancher ici.
