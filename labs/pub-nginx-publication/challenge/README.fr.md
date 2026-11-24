# Défi : publier une application avec Nginx

## La situation

Une petite application tourne sur la VM, mais Nginx ne la publie pas encore.
Le conteneur et sa configuration de départ sont prêts à être complétés.

## Mission

Configurez Nginx pour agir en reverse proxy de `app.lab.test` vers
l'application locale. Préservez le chemin et l'hôte de la requête, puis
transmettez les en-têtes attendus d'une application derrière un proxy.

## Ce qui est demandé

### Critères

- Les requêtes vers `app.lab.test` atteignent l'application locale via Nginx.
- Le chemin de requête et l'en-tête `Host` sont préservés.
- Nginx transmet les en-têtes `X-Forwarded-For` et `X-Forwarded-Proto`.

Le corrigé de référence ne figure pas dans les guides.
