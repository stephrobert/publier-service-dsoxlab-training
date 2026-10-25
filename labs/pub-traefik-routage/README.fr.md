# pub-traefik-routage

**Public :** l'apprenant.

Résolvez un enchevêtrement de routes Traefik partiellement en collision : des
priorités explicites qui se neutralisent, une application sensible joignable
depuis le mauvais nom d'hôte, et une référence inter-provider laissée non
qualifiée.

## Ce que vous saurez faire

- Fixer des priorités de routeur explicites qui reflètent la spécificité voulue.
- Restreindre une route sensible au seul nom d'hôte qui doit la servir.
- Qualifier une référence de service et de middleware entre providers.
- Vérifier qu'ajouter une route sans rapport ne casse pas les routes existantes.

Quatre backends et un Traefik partiellement mal relié sont préparés. La tâche
et les chemins disponibles sont décrits dans `/opt/pub-routage/README`.
