# publier-service-dsoxlab-training

**Langue :** [English](./README.md) · [Français](./README.fr.md)

Des labs vérifiables pour la formation
[« Publier un service web »](https://blog.stephane-robert.info/docs/services/web/)
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
- **Un hyperviseur**, parce que tous les labs sont en `runtime: vm` : soit
  **libvirt/KVM** (avec `terraform` et le provider `dmacvicar/libvirt`), soit
  **Incus**. Le provider est déclaré en liste dans [`meta.yml`](./meta.yml),
  et **une liste ne se résout pas seule** : choisissez avec
  `dsoxlab use --provider kvm`.
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
dsoxlab use --provider kvm       # une liste de providers ne se résout pas seule
dsoxlab provision                # crée edge.lab, une fois
dsoxlab list-labs                # le catalogue, dans l'ordre pédagogique
dsoxlab run       pub-01-acme-pebble
dsoxlab challenge pub-01-acme-pebble
dsoxlab check     pub-01-acme-pebble
dsoxlab clean     pub-01-acme-pebble   # défait le lab, garde la machine
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

| Lab (id) | Titre | Type | Guide associé |
|---|---|---|---|
| `pub-01-acme-pebble` | Obtenir un certificat automatiquement avec ACME | lab | guide en cours d'écriture |

## Contribuer

Lis [`CONTRIBUTING.fr.md`](./CONTRIBUTING.fr.md). En bref : un lab est prouvé
**dans les deux sens** avant d'être fusionné, `dsoxlab validate-structure` est
vert, et l'énoncé existe en anglais et en français.

Tout ce qui s'affiche est bilingue. Un document traduit d'un seul côté est
signalé par le validateur, et non laissé à la bonne volonté.

## Licence

Voir [`LICENSE`](./LICENSE).
