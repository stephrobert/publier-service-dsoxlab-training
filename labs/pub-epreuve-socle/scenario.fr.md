# Scénario

`epreuve.test` répond sur `edge.lab`, en TLS, derrière un routeur qui
relaie vers un backend protégé portant une valeur métier et sa sauvegarde.
Tout cela est en place avant votre arrivée : on vous confie un service en
fonctionnement, pas une machine vierge. Peu après sa mise en service, un
incident a été introduit, sans vous dire quelle couche il touche.

## Mission

D'abord, comprenez et documentez ce que vous observez : produisez le
dossier d'architecture du service tel qu'il est réellement. Prouvez
ensuite qu'il fonctionne, depuis `poste.lab`, le client indépendant, avec
des données que vous n'avez pas choisies à l'avance et sans jamais
relâcher la vérification TLS. En cours de route, vous constaterez que le
service ne se comporte pas comme le dossier le prétend : diagnostiquez la
cause réelle à partir de ce que vous observez, réparez par une
modification minimale, et expliquez votre raisonnement. Enfin, exercez la
sauvegarde déjà présente sur `edge.lab` : restaurez-la et montrez que le
résultat est digne de confiance, pas seulement qu'il fonctionne.
