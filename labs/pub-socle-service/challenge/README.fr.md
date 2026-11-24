# La tâche

## La situation

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

## Ce qui est demandé

Écrivez `/home/student/fiche-service.yaml` avec ces clés :

```yaml
service: <unité systemd qui sert l'application>
utilisateur: <utilisateur sous lequel tourne le processus>
ecoute: <port TCP d'écoute de l'application>
dependances:
  - nom: <unité systemd de la dépendance>
    utilisateur: <utilisateur sous lequel elle tourne>
    port: <port TCP d'écoute>
redemarrage:
  conserve: [<valeurs d'état conservées après redémarrage de l'application>]
  perdu: [<valeurs d'état perdues après redémarrage de l'application>]
recette:
  - <au moins trois critères de recette observables>
```

Les tests comparent chaque valeur au système en marche, vérifient que la
fonction métier est rétablie (`/api/livres` doit répondre HTTP 200 avec la
vraie liste) et mesurent ce qu'un redémarrage de l'application conserve. Les
valeurs d'état portent les noms renvoyés par le point d'état de l'application.
