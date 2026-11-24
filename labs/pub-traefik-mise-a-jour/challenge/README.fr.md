# Défi : mettre Traefik à niveau et revenir en arrière

## La situation

La fenêtre de changement est ouverte. Le proxy inverse utilise Traefik v3.7.6
et les utilisateurs signalent que le service publié est indisponible. Examinez
la version active, la configuration et les notes de version avant de modifier
le déploiement.

## Mission

Mettez Traefik à niveau vers la v3.7.15 avec l'image épinglée, rétablissez la
route attendue et vérifiez la réponse du service actif. Conservez une définition
de retour arrière vers la version connue comme fonctionnelle. Le contrôle
automatisé exécutera ce retour arrière, vérifiera que l'ancienne version sert
le trafic, puis restaurera la version mise à niveau.

La mise à niveau reste dans Traefik v3. Le guide de migration v2-vers-v3 donne
un contexte utile pour une future migration majeure, mais ses changements
incompatibles ne font pas partie de cette mise à jour corrective.

## Ce qui est demandé

Mettez à niveau le proxy fourni de la v3.7.6 vers la v3.7.15 sans perdre la
configuration du service. Conservez un chemin de retour vers l'image précédente
épinglée.

### Critères

- Le proxy actif utilise l'image v3.7.15 épinglée et annonce cette version.
- `upgrade.lab.test` répond HTTP 200 depuis le backend attendu.
- Le retour à l'image v3.7.6 épinglée réussit, puis la version mise à niveau
  est restaurée.

Le contrôle final change brièvement de version pour éprouver le retour arrière,
puis remet le proxy en v3.7.15. Le corrigé de référence ne figure pas dans les
guides.
