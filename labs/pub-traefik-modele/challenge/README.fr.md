# La tâche

## La situation

Traefik tourne sur `edge.lab` devant deux backends : `app-a`, atteignable
seulement par le provider fichier, et `app-b`, découvert par le provider
Docker sous le nom de service `cible`. Quelqu'un a câblé la configuration
dynamique dans la précipitation : `modele-a.lab.test` et `modele-b.lab.test`
pointent tous deux vers le même service injoignable, et un routeur attrape-tout
oublié répond à n'importe quel nom d'hôte avec `app-a`, y compris ceux que
personne n'a demandés.

## Mission

Corrigez la configuration dynamique pour que `modele-a.lab.test` atteigne
`app-a` et que `modele-b.lab.test` atteigne `app-b` via son service du
provider Docker, correctement qualifié. Supprimez ce qui fait qu'un nom non
prévu répond avec une application : il ne doit en atteindre aucune.

## Ce qui est demandé

Corrigez `/opt/pub-modele/dynamic/routes.yaml` pour que `modele-a.lab.test`
atteigne le backend `app-a`, et que `modele-b.lab.test` atteigne le service du
provider Docker nommé `cible` (pas le leurre de même nom du provider fichier).
Supprimez ce qui fait qu'un nom non prévu répond avec une application. La
notation appelle le véritable point d'entrée HTTP sur le port 80 et lit le
corps de la réponse.
