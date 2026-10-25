# pub-epreuve-socle

**Public :** l'apprenant.

C'est l'épreuve finale du socle. Aucun modèle à recopier : un service,
`epreuve.test` sur `edge.lab`, tourne déjà à votre arrivée, portant une
valeur métier et sa sauvegarde. Ce n'est pas vous qui l'avez installé. Un
incident, non annoncé, a été posé dessus après coup.

## Ce que vous saurez faire

- Produire le dossier d'architecture d'un service que vous n'avez pas
  construit : ses noms, ses flux, les identités en jeu et qui répond de
  quoi, lu par l'observation plutôt que récité de mémoire.
- Prouver que le service fonctionne depuis un client indépendant, avec des
  données que vous n'avez pas choisies à l'avance, sous une vérification
  TLS stricte, sans jamais l'affaiblir pour obtenir une réponse.
- Diagnostiquer et réparer un incident non annoncé sur une couche que l'on
  ne vous indique pas à l'avance, et montrer que votre raisonnement
  s'appuie sur ce que vous avez réellement observé.
- Exécuter une restauration depuis la sauvegarde déjà en place et montrer
  que le résultat est digne de confiance : la bonne configuration, les
  bonnes données, et une chaîne de certificats qui valide toujours
  strictement ensuite.
