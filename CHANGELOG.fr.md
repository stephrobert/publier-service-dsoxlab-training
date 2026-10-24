# Journal des modifications

Les changements notables de ce catalogue sont consignés ici. Le format suit
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et ce catalogue suit
le [versionnage sémantique](https://semver.org/lang/fr/).

**Ce qu'une version veut dire ici.** Un catalogue n'est pas une bibliothèque :
un incrément MINEUR ajoute des labs, un CORRECTIF corrige un énoncé ou un test
sans changer ce qu'un lab prouve, et un incrément MAJEUR renomme ou retire des
labs, ce qui casse la progression déjà enregistrée des apprenants.

## [1.0.0] - 2026-10-24

### Ajouté

- Des labs qui prouvent le renouvellement ACME à l'endpoint HTTPS, l'accès
  authentifié en HTTPS à l'administration Traefik avec un proxy de socket
  Docker restreint, des en-têtes de sécurité et une limitation de débit, ainsi
  que la reprise du service après le redémarrage du moteur Docker. Leurs
  corrigés de référence sont chiffrés avec `ansible-vault`.
- Un backend systemd publié avec le fournisseur fichier de Traefik, et un
  rechargement dynamique vérifié sans redémarrage du proxy.
- Un défi sur les middlewares qui mesure la réécriture des chemins, les
  redirections permanentes, les en-têtes de sécurité et la compression gzip.
  Son corrigé chiffré par Vault réussit les cinq tests ; la situation initiale
  obtient 0/100.
- Un défi d'observabilité qui vérifie les journaux d'accès JSON filtrés, une
  cible Traefik réellement active dans Prometheus et une alerte 5xx déclenchée
  par une réponse HTTP 503 ; son corrigé Vault passe 4/4 tests après 0/4 à
  l'état initial.
- Un défi de dépannage couvrant cinq pannes Traefik réelles, validé à 0/100
  avant et 100/100 après l'application du corrigé chiffré par Vault.
- Un défi de mise à niveau de Traefik de v3.7.6 à v3.7.15, avec les images
  épinglées par digest, une vérification de la configuration servie et une
  preuve de retour arrière puis de reprise. Son corrigé est chiffré avec
  `ansible-vault`.
- Une première épreuve chronométrée sans indice, qui vérifie deux services
  HTTPS depuis un client externe, le renouvellement ACME par Pebble, le blocage
  des backends et de l'administration, puis la reprise après redémarrage de
  Docker.
- Une épreuve de niveau deux chronométrée sans indice qui protège
  l'administration, vérifie la limitation de débit et les en-têtes, observe
  des réponses 5xx réelles dans les journaux JSON et Prometheus, et exige un
  diagnostic écrit d'une panne injectée.
- Un lab facultatif HAProxy 3.4 qui utilise son client ACME natif expérimental
  pour émettre et renouveler un certificat Pebble sans redémarrer le proxy ;
  le corrigé Vault réussit les quatre tests après un état initial à 0/100.
- Un lab facultatif d'observabilité HAProxy qui publie des métriques Prometheus
  privées, vérifie le scrape et la santé du backend, et limite les deux ports de
  supervision à la boucle locale. Son corrigé Vault réussit 4/4 tests après
  0/100 à l'état initial.
- Deux labs facultatifs Nginx : publication en reverse proxy avec en-têtes de
  transfert, puis durcissement avec en-têtes de sécurité, administration
  authentifiée, refus des fichiers cachés et restriction des méthodes. Les deux
  corrigés sont chiffrés par Vault ; les labs réussissent 1/1 et 4/4 tests après
  un état initial à 0/100.

### Corrigé

- Le lab canonique `pub-traefik-protection` mesure maintenant huit critères :
  la situation vulnérable obtient 0/100 et son corrigé chiffré réussit les
  huit tests.
- Le test de boucle résout les deux ports HTTP et HTTPS vers l'instance
  Traefik locale pendant le suivi des redirections ; il vérifie ainsi le proxy,
  et non le DNS externe.
- Le test de perte d'une instance de `pub-traefik-docker` tolère au plus une
  erreur transitoire pendant la fenêtre de détection, puis exige cinq secondes
  sans erreur ni trafic vers l'instance arrêtée. Rejoué le 2026-10-24 :
  0/100 avant, 100/100 après, 6/6 tests.
- Les clients TLS des tests fixent maintenant explicitement TLS 1.2 comme
  version minimale ; les tests vérifient toujours que le serveur refuse TLS
  1.0 et 1.1.

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

- Le `doc_url` du lab ACME Pebble pointait
  `/docs/services/web/certificats-acme/`, qui rend **404** : cette page
  n'existe pas, et le README du lab annonçait encore un guide « en cours
  d'écriture ». Il pointe désormais
  `/docs/services/reseau/traefik-tls-acme/`, qui rend 200 et traite le sujet.
  Une première tentative visait le pivot de la section, ce qui était une erreur
  de règle : un lab se rattache à la page qui couvre la compétence, jamais à un
  pivot.

### Manques connus

- Le lab Traefik Docker a d'abord porté un verdict **ROUGE** : le corrigé de
  référence ne passait que 5 tests sur 6. Il a ensuite été réparé et validé.

## [Non publié]

### Ajouté

- Des labs qui prouvent le renouvellement ACME à l'endpoint HTTPS, l'accès
  authentifié en HTTPS à l'administration Traefik et la reprise du service
  après le redémarrage du moteur Docker. Leurs corrigés de référence sont
  chiffrés avec `ansible-vault`.

### Corrigé

- Les tests de protection de l'administration utilisent maintenant
  l'attribut `CommandResult.rc` de Testinfra ; les cinq contrôles passent
  l'attestation bidirectionnelle.
