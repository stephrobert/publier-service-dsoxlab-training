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

<!-- LABS:START -->
### Socle : comprendre et diagnostiquer un service publié

Identifier le service derrière une réponse web, lire un échange HTTP, basculer un enregistrement DNS sans risque, puis obtenir un certificat automatiquement avec ACME.

| Lab (id) | Titre | Niveau | Runtime | Guide compagnon |
|---|---|---|---|---|
| `pub-socle-service` | Identifier le service derrière une réponse web | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/) |
| `pub-socle-http` | Lire et expliquer un échange HTTP | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/) |
| `pub-socle-dns` | Diagnostiquer et basculer un enregistrement DNS | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/) |
| `pub-acme-pebble` | Obtenir un certificat automatiquement avec ACME | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-tls-acme/) |
| `pub-socle-exposition` | Fermer les chemins qui contournent le point d'entrée | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/) |
| `pub-socle-dns-http-tls` | Dissocier nom résolu, certificat et route HTTP | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/publier-un-service/) |
| `pub-socle-reverse-proxy` | Définir les responsabilités et la confiance d'une chaîne de proxys | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/reverse-proxy/) |
| `pub-socle-tls` | Vérifier une identité TLS et sa chaîne de confiance | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/) |
| `pub-socle-application` | Réparer une session, son cookie et ses origines derrière un proxy | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/reverse-proxy/) |
| `pub-socle-flux-longs` | Observer un WebSocket et un flux d'événements | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/reverse-proxy/) |
| `pub-socle-disponibilite` | Mesurer panne, retrait et reprise d'un backend | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/reverse-proxy/) |
| `pub-socle-observabilite` | Définir un SLI et une alerte vus du client | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/) |
| `pub-socle-mise-en-service` | Réceptionner une publication et la restaurer | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/publier-un-service/) |
| `pub-socle-depannage` | Diagnostiquer une publication par couches | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/publier-un-service/) |
| `pub-epreuve-socle` | Épreuve du socle : concevoir et réceptionner un service | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/web/publier-un-service/) |

### Traefik : publier, protéger et exploiter un reverse proxy

Publier des conteneurs et des services hôte derrière Traefik, sécuriser, observer, diagnostiquer et mettre à jour le point d'entrée, puis le prouver dans les deux épreuves de niveau.

| Lab (id) | Titre | Niveau | Runtime | Guide compagnon |
|---|---|---|---|---|
| `pub-traefik-modele` | Tracer une requête dans le modèle de routage de Traefik | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik/) |
| `pub-traefik-installation` | Installer Traefik et maîtriser le cycle de vie du point d'entrée | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-installation/) |
| `pub-traefik-docker` | Publier deux conteneurs derrière Traefik, avec le fournisseur Docker | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-docker/) |
| `pub-traefik-fichier` | Publier un service systemd avec le fournisseur fichier de Traefik | niveau-1 | vm | [guide](https://doc.traefik.io/traefik/providers/file/) |
| `pub-traefik-routage` | Résoudre les priorités et collisions de routage | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik/) |
| `pub-traefik-acme` | Configurer HTTPS, le renouvellement ACME et TLS moderne dans Traefik | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-tls-acme/) |
| `pub-traefik-restart-recovery` | Maintenir un service web conteneurisé disponible après un redémarrage de Docker | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-docker/) |
| `pub-epreuve-niveau-un` | Level 1 assessment: publish and recover services | niveau-1 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-tls-acme/) |
| `pub-traefik-middlewares` | Composer et vérifier des middlewares Traefik | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-middlewares/) |
| `pub-traefik-protection` | Protéger le point d'entrée Traefik | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-securite/) |
| `pub-traefik-mtls` | Vérifier TLS backend et certificats clients | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik/) |
| `pub-traefik-flux-delais` | Borner les délais et conserver les flux applicatifs | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik/) |
| `pub-traefik-observabilite` | Observer Traefik avec des journaux JSON et Prometheus | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-observability/) |
| `pub-traefik-depannage` | Dépanner le routage et TLS dans Traefik | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-observability/) |
| `pub-traefik-mise-a-jour` | Upgrade Traefik and prove a rollback | niveau-2 | vm | [guide](https://doc.traefik.io/traefik/migrate/v2-to-v3/) |
| `pub-epreuve-niveau-deux` | Level 2 assessment: protect, observe, and diagnose | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-securite/) |
| `pub-traefik-zero-downtime` | Basculer une version de backend, prouver le retour arrière et nommer le vrai domaine de panne | niveau-2 | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/traefik-upgrade/) |

### HAProxy : publier et exploiter des services web

Publier en HTTPS avec l'ACME natif de HAProxy et l'observer avec Prometheus.

| Lab (id) | Titre | Niveau | Runtime | Guide compagnon |
|---|---|---|---|---|
| `pub-haproxy-tls` | Publish HTTPS with HAProxy native ACME | option-haproxy | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/haproxy/) |
| `pub-haproxy-observabilite` | Observe HAProxy with Prometheus | option-haproxy | vm | [guide](https://www.stephane-robert.info/docs/services/reseau/haproxy/) |

### Nginx : publier et protéger des services web

Publier une application avec Nginx et la protéger.

| Lab (id) | Titre | Niveau | Runtime | Guide compagnon |
|---|---|---|---|---|
| `pub-nginx-publication` | Publish an application with Nginx | option-nginx | vm | [guide](https://www.stephane-robert.info/docs/services/web/nginx/) |
| `pub-nginx-protection` | Protect an application with Nginx | option-nginx | vm | [guide](https://www.stephane-robert.info/docs/services/web/nginx/) |

_36 labs, table générée par `scripts/gen_catalog.py`._
<!-- LABS:END -->

### Alignement sur la feuille de route

La cible d'origine était de **11 labs de cœur plus quatre labs facultatifs**,
soit 15 labs, tous implémentés et validés. Le contrat de la formation
(`publier-service`, v2) en prévoit désormais 67 : le catalogue ci-dessus
contient les 36 écrits à ce jour, chacun validé de 0 à 100
(`validation-labs.json`). Les sections Nginx et HAProxy sont encore courtes et
continuent de grandir.

## Contribuer

Lis [`CONTRIBUTING.fr.md`](./CONTRIBUTING.fr.md). En bref : un lab est prouvé
**dans les deux sens** avant d'être fusionné, `dsoxlab validate-structure` est
vert, et l'énoncé existe en anglais et en français.

Tout ce qui s'affiche est bilingue. Un document traduit d'un seul côté est
signalé par le validateur, et non laissé à la bonne volonté.

## Licence

Voir [`LICENSE`](./LICENSE).
