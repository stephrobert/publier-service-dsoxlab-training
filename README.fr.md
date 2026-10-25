# Formation Publier un service web : un reverse proxy, et des certificats qui se renouvellent

**Langue :** [English](./README.md) · [Français](./README.fr.md)

[![CI](https://github.com/stephrobert/publier-service-dsoxlab-training/actions/workflows/ci.yml/badge.svg)](https://github.com/stephrobert/publier-service-dsoxlab-training/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/stephrobert/publier-service-dsoxlab-training?label=OpenSSF%20Scorecard)](https://securityscorecards.dev/viewer/?uri=github.com/stephrobert/publier-service-dsoxlab-training)
[![Plumber compliance](https://score.getplumber.io/github.com/stephrobert/publier-service-dsoxlab-training.svg)](https://score.getplumber.io/github.com/stephrobert/publier-service-dsoxlab-training)
[![SLSA 3](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)
[![Licence : CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](./LICENSE)

Des labs vérifiables pour la formation
[« Publier un service web »](https://www.stephane-robert.info/docs/services/web/)
du blog, joués avec [dsoxlab](https://github.com/stephrobert/dsoxlab).

## Ce que c'est

À la fin, l'apprenant sait placer un reverse proxy devant des services qui ne
sont pas joignables seuls, et lui obtenir un certificat de confiance sans
toucher un fichier à la main. Pas une liste de sujets : chaque lab se termine
sur quelque chose d'observable, comme un certificat que les tests analysent ou
une réponse que le proxy sert.

L'ordre compte : un proxy qui publie en HTTPS a besoin d'un certificat, donc
le lab des certificats vient d'abord, face à une autorité de test qui ne
touche jamais l'internet public.

**Un lab est noté sur l'état du système, jamais sur les commandes tapées.**
L'apprenant atteint le résultat par le chemin qu'il choisit.

## Prérequis

- **Python 3.11+ et [`uv`](https://docs.astral.sh/uv/)**
- **`git`**
- **`dsoxlab`**, le moteur, installé en outil autonome (voir plus bas).
- **Un hyperviseur**, parce que tous les labs sont en `runtime: vm` :
  **libvirt/KVM** (avec `terraform` et le provider `dmacvicar/libvirt`) est le
  provider par défaut, déclaré dans [`meta.yml`](./meta.yml). Pour utiliser
  Incus à la place, remplacez `infra.provider: kvm` par `infra.provider: incus`
  avant de provisionner.
- **4 Go de RAM libre et 20 Go de disque** pour l'unique machine, `edge.lab`.
- **Un accès réseau sortant** au premier `provision`, pour tirer l'image de
  base et les images de conteneurs.

Une machine virtuelle, `edge.lab` (Ubuntu 24.04, 2 vCPU, 4 Go, 20 Go),
déclarée dans `meta.yml` et créée par `dsoxlab provision`. Docker, les proxys
et l'autorité de certification de test y tournent : rien ne tourne sur votre
poste, et les ports 80 et 443 de votre hôte restent libres.

`dsoxlab doctor` dit ce dont ce dépôt a besoin et ce dont il n'a pas besoin, et
distingue un contrôle qui a échoué d'un contrôle qu'il n'a pas pu mesurer.

## Installation

`dsoxlab` est publié sur [PyPI](https://pypi.org/project/dsoxlab/).
Installe-le en outil autonome, pour qu'il reste hors de ce dépôt :

```bash
# 1. La CLI dsoxlab (outil externe, hors de ce dépôt)
uv tool install dsoxlab

# 2. Ce catalogue de labs
git clone https://github.com/stephrobert/publier-service-dsoxlab-training.git
cd publier-service-dsoxlab-training

# 3. Vérifier le contrat et la machine
dsoxlab validate-structure
dsoxlab doctor
```

### Votre premier lab, en cinq minutes

```bash
export LAB_HOME=$PWD
dsoxlab provision                # crée edge.lab, une fois
dsoxlab list-labs                # le catalogue, dans l'ordre pédagogique
dsoxlab run       pub-acme-pebble
dsoxlab challenge pub-acme-pebble
dsoxlab check     pub-acme-pebble
dsoxlab clean     pub-acme-pebble   # défait le lab, garde la machine
```

C'est `run` qui prépare le lab. Un `check` joué sur un lab jamais démarré ne
mesure rien, et le dit au lieu d'enregistrer un 0.

### Garder à jour

```bash
uv tool upgrade dsoxlab        # le moteur, publié sur PyPI
git -C <ce dépôt> pull         # le catalogue
```

Le moteur et le catalogue avancent indépendamment : un nouveau `dsoxlab` ne
demande jamais de recloner les labs, et de nouveaux labs ne demandent jamais de
mettre l'outil à jour, tant que la version du contrat correspond.

## Comment ça marche

### Le contrat déclaratif, à deux niveaux

Le catalogue est décrit par des données, pas par du code, et c'est ce qui garde
le moteur `dsoxlab` indépendant du domaine :

- **`meta.yml`** à la racine déclare l'identité du dépôt et l'**ordre** des
  sections affichées par `list-labs` ;
- **`lab.yaml`** par lab déclare ses `skills`, son `level`, son `runtime`
  (type, fixtures, services), ses `distros`, son `doc_url` et un bloc
  `validation`. Un `lab.fr.yaml` surcharge `title` et `description` en
  français, et rien d'autre.

`dsoxlab validate-structure` contrôle tout le contrat : `meta.yml` bien formé,
chaque lab référencé présent avec un `lab.yaml` valide, chaque fichier de test
et de fixture déclaré réellement là, et chaque lien relatif d'un README qui
mène quelque part.

### Le cycle de vie d'un lab

```bash
dsoxlab list-labs              # parcourir le catalogue
dsoxlab show      <id>         # métadonnées et état d'un lab
dsoxlab run       <id>         # poser l'état de départ
dsoxlab challenge <id>         # lire la mission, sans pas-à-pas
dsoxlab hint      <id>         # révéler un indice (déduit du score)
dsoxlab check     <id>         # lancer les tests, calculer et enregistrer le score
dsoxlab clean     <id>         # défaire ce que le lab a posé
dsoxlab progress               # avancement par section, score moyen
```

### Les runtimes

Tous les labs sont en `vm` : les conteneurs appartiennent à la machine, pas à
l'hôte de l'apprenant.

| Runtime | Ce que le lab demande |
|---|---|
| `vm` | la machine `edge.lab`, créée par `dsoxlab provision`, sous Ubuntu 24.04. Docker et les conteneurs y tournent, lancés par le `setup.yaml` du lab. |

### Le modèle de validation

La validation **prouve l'état, elle ne fait pas confiance à l'apprenant**.
Chaque lab porte des tests `pytest` sous `challenge/tests/` qui lisent ce que
le système contient, jamais ce qu'un fichier contient ni quelles commandes ont
été tapées.

Et un lab est prouvé **dans les deux sens** : les tests doivent échouer avant
le travail et passer après. Un test vert avant le travail n'est pas un test,
c'est une hypothèse sur le setup.

Les solutions de référence vivent sous `solution/<lab>/`, chiffrées avec
`ansible-vault` ; le mot de passe (`.vault-pass` à la racine) n'est jamais
versionné. Une solution en clair gâcherait le lab, et git la garde pour
toujours.

La CI GitHub vérifie le contrat, les workflows et la qualité du dépôt, mais ne
provisionne aucune VM et ne rejoue pas les labs. Son badge ne vaut donc pas
attestation pédagogique : le cycle runtime 0 → 100 est vérifié séparément avec
`python3 scripts/valider-labs.py --lab <id>` sur une infrastructure provisionnée.

### Score, indices, avancement

`check` enregistre un score (tests réussis sur total, moins le coût des indices
révélés). Les indices sont **en base64** dans `challenge/hints.yaml`, pour qu'on
n'y accède pas en ouvrant le fichier, et leur coût croît avec leur précision.
L'historique vit dans une base SQLite **locale à ce dépôt**.

Une exécution qui n'a rien mesuré n'est ni une réussite ni un échec : si tous
les tests collectés skippent, `check` n'enregistre aucune note et dit pourquoi.
Un 0 accuserait le lab de ce qui manque au poste.

## Catalogue

À jouer dans l'ordre. D'autres labs s'ajoutent à mesure qu'ils sont écrits et
prouvés dans les deux sens.

### Niveau 1 : publier des services derrière un reverse proxy

| Lab | Ce qu'il prouve |
|---|---|
| `pub-acme-pebble` | un certificat est émis par une autorité ACME de test après un défi HTTP-01 | lab, 30 min |
| `pub-traefik-docker` | deux conteneurs sont publiés derrière Traefik, découverts par la socket Docker | lab, 40 min |
| `pub-traefik-fichier` | Traefik route dynamiquement vers un service systemd de l'hôte sans redémarrage | lab, 30 min |
| `pub-traefik-acme` | Traefik renouvelle et sert un certificat ACME, redirige HTTP, protège le stockage et refuse TLS 1.0/1.1 | lab, 40 min |
| `pub-traefik-restart-recovery` | un service web conteneurisé revient après le redémarrage du moteur Docker | lab, 30 min |
| `pub-epreuve-niveau-un` | épreuve chronométrée : deux services HTTPS, renouvellement, filtrage externe et reprise de Docker | épreuve, 60 min |

### Niveau 2 : protéger et exploiter un reverse proxy

| Lab | Ce qu'il prouve |
|---|---|
| `pub-traefik-middlewares` | réécriture de chemin, redirections permanentes, en-têtes de sécurité, réponses compressées et mise à jour sans redémarrage | lab, 40 min |
| `pub-traefik-protection` | administration HTTPS authentifiée, proxy de socket Docker restreint, en-têtes de sécurité et limitation de débit | lab, 45 min |
| `pub-traefik-observabilite` | journaux JSON filtrés, cible de métriques Prometheus active et alerte déclenchée par une réponse 5xx réelle | lab, 40 min |
| `pub-traefik-depannage` | diagnostiquer et réparer le routage, le backend, le délai, le certificat et les redirections | lab, 45 min |
| `pub-traefik-mise-a-jour` | mettre Traefik à niveau, vérifier la configuration servie et prouver le retour arrière | lab, 25 min |
| `pub-epreuve-niveau-deux` | épreuve chronométrée : protéger et observer un proxy, puis résoudre un incident inconnu | épreuve, 75 min |

### Option : HAProxy

| Lab | Ce qu'il prouve |
|---|---|
| `pub-haproxy-tls` | émission et renouvellement ACME natifs (fonction expérimentale), terminaison TLS, SNI et redirection HTTP vers HTTPS | lab, 40 min |
| `pub-haproxy-observabilite` | métriques HAProxy privées, collecte Prometheus active et ports de supervision limités à la boucle locale | lab, 35 min |

### Option : Nginx

| Lab | Ce qu'il prouve |
|---|---|
| `pub-nginx-publication` | publication en reverse proxy avec préservation de l'hôte, du chemin et des en-têtes de transfert | lab, 30 min |
| `pub-nginx-protection` | en-têtes de sécurité, administration authentifiée, refus des fichiers cachés et limitation des méthodes HTTP | lab, 35 min |

### Alignement sur la feuille de route

La cible reste **11 labs de cœur (neuf labs de leçon et deux épreuves), plus
quatre labs facultatifs**, soit 15 labs dans le parcours. Les 11 labs de cœur
et les quatre options sont implémentés et validés. L'exercice de renouvellement
est intégré au lab ACME prévu ; l'exercice d'administration couvre désormais
l'authentification HTTPS, l'isolation du socket Docker, les en-têtes de
sécurité et la limitation de débit. Le lab sur les middlewares couvre aussi la
réécriture des chemins, les redirections, les en-têtes et la compression.
L'exercice de reprise après redémarrage est une preuve intermédiaire, jouable
séparément, dont le résultat est réutilisé dans la première épreuve plutôt que
compté comme un lab de cœur supplémentaire. Les 16 labs jouables, y compris
cette preuve intermédiaire, passent le cycle de validation de 0 à 100.

## Contribuer

Lis [`CONTRIBUTING.fr.md`](./CONTRIBUTING.fr.md). En bref : un lab est prouvé
**dans les deux sens** avant d'être fusionné, `dsoxlab validate-structure` est
vert, et l'énoncé existe en anglais et en français.

Tout ce qui s'affiche est bilingue. Un document traduit d'un seul côté est
signalé par le validateur, et non laissé à la bonne volonté.

## Licence

Voir [`LICENSE`](./LICENSE).
