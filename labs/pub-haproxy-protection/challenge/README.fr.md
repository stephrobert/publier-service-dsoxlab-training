# Défi : protéger le frontend HAProxy

## Critères

- `/admin` répond `200` depuis `127.0.0.1` et `403` depuis l'adresse réseau
  de la VM.
- Chaque réponse porte `X-Content-Type-Options: nosniff` et
  `X-Frame-Options: DENY`.
- Un client qui dépasse 20 requêtes en 10 secondes reçoit `429`.
- Les requêtes ordinaires vers l'application répondent toujours `200`.

Le corrigé de référence ne figure pas dans les guides.
