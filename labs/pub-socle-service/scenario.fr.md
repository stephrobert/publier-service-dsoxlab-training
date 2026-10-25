# Scénario

Une application de catalogue tourne sur `edge.lab`. Sa page d'accueil
s'affiche, son contrôle de santé répond `ok`, et pourtant la liste des livres
renvoie une erreur. Personne ne peut vous dire quel processus répond, sous
quel utilisateur, sur quel port, ni de quoi il dépend. Vous reprenez le
service.

## Mission

Rédigez la fiche de service de l'application dans
`/home/student/fiche-service.yaml`, rétablissez la fonction métier, puis
démontrez l'effet d'un redémarrage sur l'état de l'application. Partez de ce
que le système indique, pas de ce que vous supposez.
