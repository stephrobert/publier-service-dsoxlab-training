# Défi : observer Traefik

Traefik sert `observabilite.lab.test` ; le chemin backend `/fail` répond
volontairement HTTP 503. Prometheus scrute déjà la cible locale configurée
dans `/opt/pub-observabilite/prometheus/prometheus.yml`.

## Critères

- Écrire les journaux d'accès Traefik en JSON dans
  `/opt/pub-observabilite/logs/access.json`.
- Filtrer le journal sur les réponses HTTP 5xx et conserver l'hôte, le chemin
  et le statut aval. Ne pas journaliser les en-têtes des requêtes.
- Activer les métriques Prometheus Traefik sur un point d'entrée local à
  `127.0.0.1:8082`, avec les labels de routeur et de point d'entrée.
- Configurer une alerte Prometheus déclenchée par une réponse HTTP 5xx de
  Traefik, puis recharger Prometheus après la modification des règles.
- Garder l'interface et l'API Prometheus liées à l'interface de boucle locale.

Les tests génèrent du trafic HTTP réel et inspectent le journal JSON et l'API
HTTP de Prometheus. Ils n'imposent ni nom d'alerte ni organisation de fichiers.
