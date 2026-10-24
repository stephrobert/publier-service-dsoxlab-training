# Défi : mettre Traefik à niveau et revenir en arrière

Mettez à niveau le proxy fourni de la v3.7.6 vers la v3.7.15 sans perdre la
configuration du service. Conservez un chemin de retour vers l'image précédente
épinglée.

## Critères

- Le proxy actif utilise l'image v3.7.15 épinglée et annonce cette version.
- `upgrade.lab.test` répond HTTP 200 depuis le backend attendu.
- Le retour à l'image v3.7.6 épinglée réussit, puis la version mise à niveau
  est restaurée.

Le contrôle final change brièvement de version pour éprouver le retour arrière,
puis remet le proxy en v3.7.15. Le corrigé de référence ne figure pas dans les
guides.
