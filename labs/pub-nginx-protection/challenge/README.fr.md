# Défi : renforcer le proxy applicatif Nginx

## Critères

- Les réponses contiennent `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` et une politique CSP restrictive.
- `/admin` exige une authentification et publie toujours le backend pour un
  utilisateur authentifié.
- Les fichiers cachés sont refusés.
- `DELETE` est refusée sans empêcher les requêtes applicatives normales.

Le corrigé de référence ne figure pas dans les guides.
