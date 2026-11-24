# Épreuve : protéger, observer et diagnostiquer

## La situation

Vous prenez en charge un déploiement Traefik que vous ne connaissez pas. Les
utilisateurs signalent que le service `app.lab.test` est indisponible. La route
d'administration n'a pas été revue et le proxy ne dispose pas d'une supervision
exploitable.

## Mission

En 75 minutes, sécurisez l'administration, ajoutez des en-têtes de sécurité et
une limitation de débit, configurez les journaux JSON filtrés et les métriques
Prometheus avec une alerte sur les réponses 5xx, puis rétablissez l'application.

L'incident initial n'est pas documenté. Appuyez-vous sur la réponse HTTP
observée et les journaux Traefik pour identifier le composant défaillant.
Consignez le symptôme, la preuve tirée des journaux, la cause, la correction et
la réponse obtenue après réparation dans
`/opt/pub-epreuve-niveau-deux/incident-report.txt`.

Aucun indice n'est fourni. Le corrigé de référence ne figure pas dans les
guides.

## Ce qui est demandé

### Critères

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
