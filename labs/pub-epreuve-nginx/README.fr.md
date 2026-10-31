# pub-epreuve-nginx

**Public :** l'apprenant.

C'est l'épreuve de fin du module Nginx. Aucun modèle à recopier : on vous
remet un Nginx vide, un site statique, une API et une autorité ACME locale, et
vous publiez puis exploitez le service sous deux noms. Un incident, non
annoncé, est injecté après votre recette initiale.

## Ce que vous saurez faire

- Publier un site statique et une API sous deux noms, avec une chaîne HTTPS
  validée strictement et un renouvellement qui renouvelle vraiment, sans jamais
  affaiblir la validation.
- Fermer l'administration et le backend, refuser ce que le service n'utilise
  pas, et mettre en cache les réponses publiques sans jamais mélanger deux
  sessions.
- Livrer un flux long au rythme du backend, journaliser des durées qui
  mesurent, et lever une alerte qui sonne puis retombe.
- Diagnostiquer et réparer un incident non annoncé sans perdre une garantie.
- Prouver un plan de reprise : restaurer depuis une sauvegarde, redémarrer,
  rejouer la recette.

```bash
dsoxlab run pub-epreuve-nginx
dsoxlab check pub-epreuve-nginx
```
