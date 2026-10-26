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

## Ce que la machine note, et ce qu'un relecteur lit

Cette distinction n'est pas une formalité : une machine ne sait pas juger
un document, et prétendre le contraire reviendrait à valider un texte
incohérent au motif qu'il est assez long et qu'il emploie les bons mots.

**Noté par la validation**, parce que cela se compare à l'état réel de la
machine :

- le dossier **existe** et **nomme le service** qu'il documente ;
- le service répond depuis `poste.lab` avec une donnée choisie au moment
  de l'essai, sous vérification TLS stricte, et `/admin` reste refusé ;
- le champ **`couche`** de `incident.yaml` désigne la couche réellement
  cassée, et le champ **`composant`** nomme le composant fautif sans citer
  de couche sans rapport ;
- le champ **`explication`** est **présent** ;
- la restauration s'exécute et le résultat est vérifiable.

**Lu par un relecteur, et non noté ici** : la pertinence du dossier, sa
couverture des noms, des flux, des identités et des responsabilités, et la
qualité du raisonnement écrit dans `explication`. Les hypothèses que vous
avez écartées ont leur place dans ce champ : les y écrire ne vous pénalise
pas, c'est au contraire ce qu'on attend d'un diagnostic.
