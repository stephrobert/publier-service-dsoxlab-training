# pub-traefik-modele

**Public :** l'apprenant.

Apprenez à lire le modèle de routage de Traefik : comment un point d'entrée,
un routeur et un service s'enchaînent, et comment un nom non qualifié se
résout entre deux providers.

## Ce que vous saurez faire

- Suivre une requête du point d'entrée jusqu'au backend, via routeur et service.
- Qualifier une référence inter-provider avec `@file` ou `@docker`.
- Vérifier qu'un nom non prévu n'atteint aucune application.

Deux backends et un Traefik partiellement mal relié sont préparés. La tâche et
les chemins disponibles sont décrits dans `/opt/pub-modele/README`.
