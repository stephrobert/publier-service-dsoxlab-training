# The task

1. Send the recette request described in `/home/student/README-api`: a `POST`
   on `/commandes` carrying the recette token both in a header
   `X-Recette: <token>` and in the JSON body (`{"jeton": "<token>"}`).
2. Write `/home/student/recette-http.yaml`:

```yaml
redirections:        # method the backend receives when curl follows the redirect of a POST
  301: <GET or POST>
  302: <GET or POST>
  303: <GET or POST>
  307: <GET or POST>
  308: <GET or POST>
statuts:             # status code returned by each route
  /refus: <code>
  /erreur: <code>
  /inconnue: <code>
```

3. Write `/home/student/envoyer-commande.sh`, run as
   `bash envoyer-commande.sh <api-url> <ref>`. It must create the order `<ref>`
   exactly once and exit 0, even if the API wrote the order and the response
   never came back.

The tests replay the redirects themselves, send fresh references (some with a
lost response) and count the writes the API really performed.
