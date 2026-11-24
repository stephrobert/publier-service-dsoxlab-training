# Défi : renforcer le proxy applicatif Nginx

## La situation

Nginx publie déjà l'application, mais le proxy accepte les requêtes
d'administration sans protection, sert les fichiers cachés et transmet des
méthodes dont l'application n'a pas besoin.

## Mission

Ajoutez les en-têtes de sécurité, exigez les identifiants fournis sur
`/admin`, refusez les fichiers cachés et bloquez les méthodes d'écriture
inutiles sans casser les requêtes normales de l'application.

## Ce qui est demandé

### Critères

- Les réponses contiennent `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` et une politique CSP restrictive.
- `/admin` exige une authentification et publie toujours le backend pour un
  utilisateur authentifié.
- Les fichiers cachés sont refusés.
- `DELETE` est refusée sans empêcher les requêtes applicatives normales.

Le corrigé de référence ne figure pas dans les guides.
