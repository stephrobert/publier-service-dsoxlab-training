# Défi : limiter et observer le proxy Nginx

## Critères

- Une rafale de requêtes d'un même client reçoit `429` pour une partie
  d'entre elles, alors qu'une requête isolée après la rafale reçoit `200`.
- `/opt/pub-nginx-observation/logs/access.log` contient un objet JSON par
  ligne avec `time`, `remote_addr`, `request_uri`, `status` et
  `request_time`.
- `stub_status` répond sur `127.0.0.1:8081` et le port n'est pas joignable
  depuis le réseau.
- L'application reste publiée sur le port 80.

Le corrigé de référence ne figure pas dans les guides.
