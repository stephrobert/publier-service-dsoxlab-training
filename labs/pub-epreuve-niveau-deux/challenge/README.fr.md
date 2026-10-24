# Épreuve : protéger, observer et diagnostiquer

## Critères

- La route de l'application répond HTTP 200 après réparation de la panne
  inconnue.
- Le tableau de bord exige une authentification ; sans identifiants, la réponse
  est HTTP 401.
- Les réponses de l'application portent les en-têtes de sécurité requis et une
  rafale de requêtes déclenche HTTP 429.
- Les journaux JSON ne conservent que les réponses 5xx et omettent les champs
  d'en-têtes des requêtes.
- Prometheus déclare la cible Traefik active et déclenche une alerte après un
  véritable HTTP 503.
- `incident-report.txt` consigne le statut observé, la preuve issue des
  journaux, le diagnostic, la correction et la réponse obtenue.
- L'épreuve est terminée en 75 minutes ; aucun indice n'est fourni.

Le corrigé de référence ne figure pas dans les guides.
