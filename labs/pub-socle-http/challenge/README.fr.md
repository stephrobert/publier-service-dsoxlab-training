# La tâche

1. Envoyez la requête de recette décrite dans `/home/student/README-api` : un
   `POST` sur `/commandes` portant le jeton de recette dans un en-tête
   `X-Recette: <jeton>` et dans le corps JSON (`{"jeton": "<jeton>"}`).
2. Écrivez `/home/student/recette-http.yaml` :

```yaml
redirections:        # méthode reçue par le backend quand curl suit la redirection d'un POST
  301: <GET ou POST>
  302: <GET ou POST>
  303: <GET ou POST>
  307: <GET ou POST>
  308: <GET ou POST>
statuts:             # code renvoyé par chaque route
  /refus: <code>
  /erreur: <code>
  /inconnue: <code>
```

3. Écrivez `/home/student/envoyer-commande.sh`, lancé par
   `bash envoyer-commande.sh <url-api> <ref>`. Il doit créer la commande
   `<ref>` exactement une fois et sortir en 0, même si l'API a écrit la
   commande et que la réponse n'est jamais revenue.

Les tests rejouent eux-mêmes les redirections, envoient des références neuves
(certaines avec une réponse perdue) et comptent les écritures réellement
faites par l'API.
