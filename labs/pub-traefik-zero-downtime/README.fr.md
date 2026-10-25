# pub-traefik-zero-downtime

**Public :** l'apprenant.

Basculez une version de backend avec des erreurs bornées, retirez une
candidate malsaine de la rotation et revenez en arrière, prouvez
honnêtement quelle panne un point d'entrée redondant survit réellement, et
corrigez un outil de rotation de certificat pour que deux points d'entrée
partageant le même stockage de certificat ne servent jamais une paire
corrompue.

## Ce que vous saurez faire

- Déplacer le trafic réel d'une version de backend vers une candidate avec
  un service Traefik pondéré, plutôt qu'une bascule tout ou rien.
- Ajouter une sonde de santé au répartiteur pour qu'une candidate malsaine
  soit réellement retirée de la rotation, et s'en servir pour un vrai
  retour arrière.
- Distinguer la panne qu'un point d'entrée redondant survit (perdre l'un
  de plusieurs processus) de celle qu'il ne survit pas (perdre l'hôte
  unique qui les porte tous), et prouver les deux plutôt que d'en supposer
  une.
- Reconnaître pourquoi partager un même stockage de certificat entre
  plusieurs points d'entrée exige un traitement explicite de la
  concurrence, et corriger un outil qui en manquait.

Deux points d'entrée Traefik et deux versions d'un backend sont préparés.
La tâche et les chemins disponibles sont décrits dans `/opt/pub-zds/README`.

**Limite honnête de ce lab :** le contrat demande deux points d'entrée sur
deux VM distinctes. Seule `edge.lab` est disponible ici, donc les deux
points d'entrée tournent réellement sur elle (voir la recette). Ce lab
transforme cette limite en la leçon du point « edge », plutôt que de la
cacher : il vous demande de prouver, et de déclarer par écrit, quelle
panne survit et laquelle ne survit pas, plutôt que de prétendre à une
résilience au niveau de l'hôte que ce montage à une seule VM ne peut pas
fournir.
