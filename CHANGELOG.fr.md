# Journal des modifications

Les changements notables de ce catalogue sont consignés ici. Le format suit
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et ce catalogue suit
le [versionnage sémantique](https://semver.org/lang/fr/).

**Ce qu'une version veut dire ici.** Un catalogue n'est pas une bibliothèque :
un incrément MINEUR ajoute des labs, un CORRECTIF corrige un énoncé ou un test
sans changer ce qu'un lab prouve, et un incrément MAJEUR renomme ou retire des
labs, ce qui casse la progression déjà enregistrée des apprenants.

## [1.0.0] - 2026-10-26

### Ajouté le 2026-10-26

- **Le parcours Nginx au complet, dix labs**, et **le parcours HAProxy au
  complet, onze labs**. Les deux séries vont de l'installation au dépannage
  et à la mise à jour, et chacune se termine par un lab qui redémarre la
  machine : un service qui répond aujourd'hui et ne revient pas demain n'est
  pas installé, il est lancé.

  Chaque lab porte son corrigé de référence chiffré, quatre indices
  bilingues à coût croissant, et des tests qui mesurent l'état du système
  plutôt que les commandes tapées. **Aucun des vingt et un n'est attesté**,
  et c'est écrit ici plutôt que laissé à découvrir : ils ont été éprouvés
  par relecture et par exécution de leurs composants pris séparément, pas de
  bout en bout sur une VM.

- **Une seconde machine d'entrée, `edge2.lab`**, ajoutée en fin de
  `infra.hosts`. Elle ne sert qu'à `pub-haproxy-ha` : prouver un domaine de
  panne demande deux machines, et une seule ne prouve que la perte d'un
  processus. Le contrat `infra:` étant commun au dépôt, tous les labs
  démarrent désormais trois VM au lieu de deux, soit 7 Go de mémoire au lieu
  de 5.

### Corrigé le 2026-10-26

- **`pub-nginx-tls` affirmait qu'une redirection globale vers HTTPS empêche
  la validation d'un défi HTTP-01.** C'est trop affirmatif : le validateur
  de Let's Encrypt suit les redirections, jusqu'à dix, vers les ports 80 et
  443, et ne vérifie pas le certificat de la cible. L'énoncé dit maintenant
  ce qui reste vrai quelle que soit l'autorité, à savoir qu'une redirection
  place le défi hors du contrôle de celui qui l'écrit, qu'elle échoue à la
  première émission puisque rien n'écoute encore en 443, et qu'elle casse
  dès que la cible sort des deux ports autorisés.

- **`pub-nginx-tls` livrait un corrigé injouable.** Il employait `http2 on;`,
  forme qui n'existe qu'à partir de Nginx 1.25.1, alors que les labs
  tournent sur le paquet d'Ubuntu 24.04, soit 1.24. Une directive inconnue
  n'est pas ignorée : elle fait échouer `nginx -t`, donc tout le fichier.

### Ajouté le 2026-10-25

- **Deux labs que des pages publiées citaient déjà et qui n'existaient pas** :
  `pub-haproxy-protection` et `pub-nginx-observation`. Un lecteur qui suivait
  `nginx-proteger-observer` ou `haproxy-proteger-observer` était envoyé vers
  un exercice introuvable. Les deux arrivent avec un corrigé de référence
  chiffré et quatre indices bilingues à coût croissant ; aucun des deux n'est
  encore attesté, et le CHANGELOG le dit plutôt que de le laisser découvrir.

  `pub-haproxy-protection` porte sur ce que HAProxy sait faire et que le lab
  Nginx ne couvre pas : la limite de débit par source, avec une
  `stick-table`. Son test central prouve trois choses à la fois, parce
  qu'aucune ne suffit seule : une rafale de 40 requêtes doit rencontrer des
  429 **et** des 200 (des 429 seuls diraient une porte fermée, des 200 seuls
  une absence de limite), et le service doit revenir une fois la fenêtre
  écoulée, parce qu'une limite de débit relâche.

  `pub-nginx-observation` repose sur une idée : observer n'est pas écrire des
  champs. Un journal où `request_time` vaudrait toujours `0.000` serait
  structuré, parsable et inutile. Le backend sert donc une page qui dort deux
  secondes et une qui répond 503, et les tests confrontent la valeur
  journalisée à ces faits.

- **Les indices des quatre labs d'option qui n'en avaient pas**
  (`pub-nginx-publication`, `pub-nginx-protection`, `pub-haproxy-tls`,
  `pub-haproxy-observabilite`), et les sept `lab.fr.yaml` manquants. Les deux
  épreuves chronométrées restent sans indices : leur scénario annonce qu'il
  n'en est fourni aucun, donc leur absence est une règle du lab et non un
  oubli.

- **`scripts/chiffrer-solutions.sh`**, que tous les catalogues frères avaient.
  Les corrigés n'existaient ici que chiffrés : en lire un demandait un
  `ansible-vault view` à la main, en modifier un un aller-retour que rien ne
  guidait. Une solution dont le clair n'a pas changé n'est pas rechiffrée :
  le chiffré change à chaque passage, et le recalculer sans raison ferait
  passer le lab pour modifié et son attestation pour périmée.

- **Un hook `ruff`.** La section `[tool.ruff]` était dans le pyproject depuis
  l'origine, mais aucun hook ne l'appelait : onze erreurs dormaient dans
  quatre labs, dont un `zip()` sans `strict=` et une variable nommée `l`. Une
  configuration que rien ne joue n'est pas une règle, c'est une intention.
  Les onze sont corrigées.

### Corrigé le 2026-10-25

- **`pub-traefik-mtls` concluait sur « un statut différent de 200 ».** Mesuré
  par contre-test : ce critère tient **sept situations sur dix** pour un refus
  TLS, dont un service éteint, un fichier de certificat illisible et un 404 de
  routage. Avec le backend invalide répondant 404, le test du backend passait
  au vert sans avoir démontré le moindre refus. Les tests lisent désormais
  aussi le code de sortie de curl, qui sépare ce que le code HTTP confond, et
  `tests/test_discriminant_mtls.py` rejoue les dix situations à chaque commit.

- **`pub-epreuve-socle` notait deux choses qu'il ne pouvait pas juger.** Le
  dossier d'architecture était noté à un seuil de 200 caractères et à quelques
  mots attendus : un texte incohérent assez long et saupoudré de « tls »,
  « certificat » et « responsab » validait l'épreuve. Et le diagnostic
  cherchait son mot-clé dans `composant` **et** `explication` réunis, si bien
  que le champ structuré pouvait rester vide pendant que de la prose libre
  emportait le point, tandis qu'un apprenant qui écrivait proprement les
  hypothèses qu'il avait **écartées** se faisait recaler par le contrôle
  « tout citer à la fois n'est pas un diagnostic ». La note porte désormais
  sur les champs structurés comparés au secret ; la prose est exigée présente
  et déclarée non notée, et les deux scénarios annoncent la distinction.

- **`pub-socle-exposition` classait « fermé » un service joignable.** Sa sonde
  lisait le corps de la réponse, donc un service répondant **204 No Content**
  était rapporté comme un port fermé. Elle lit maintenant `%{http_code}`.

### Manques connus

- `pub-haproxy-protection` et `pub-nginx-observation` n'ont aucune entrée dans
  `validation-labs.json` : les attester demande les machines du lab et une
  campagne dédiée. Les trois labs corrigés ci-dessus, et les quatre dont les
  tests ont été touchés par la passe de lint, sont à rejouer pour la même
  raison.

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
