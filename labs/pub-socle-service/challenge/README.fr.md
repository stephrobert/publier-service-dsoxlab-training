# La tâche

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
