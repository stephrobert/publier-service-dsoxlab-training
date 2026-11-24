# La tâche

## La situation

Traefik tourne sur `edge.lab` devant quatre backends : une application par
défaut, une API v2 censée prendre le relais sous `/v2`, un panneau
d'administration qui ne doit répondre que sur son propre nom d'hôte, et un
catalogue découvert par le provider Docker. Quelqu'un a écrit des priorités
explicites sans vérifier quel routeur devait réellement l'emporter, a laissé
le panneau d'administration sans restriction de nom d'hôte, et a référencé le
service et le middleware du catalogue sans qualifier de quel provider ils
viennent.

## Mission

Corrigez les priorités des routeurs pour que `/v2` atteigne l'API v2 au lieu
de l'application par défaut. Restreignez le panneau d'administration à son
nom d'hôte prévu : aucun autre nom ne doit l'atteindre. Qualifiez les
références de service et de middleware du catalogue vers le provider Docker.
Prouvez ensuite qu'ajouter une route de plus, sans rapport, ne perturbe
aucune des routes que vous avez corrigées.

## Ce qui est demandé

Corrigez `/opt/pub-routage/dynamic/routes.yaml`. Le routeur par défaut ne doit
l'emporter que si aucune règle plus spécifique ne s'applique : montez la
priorité de `api-v2` au-dessus de celle de `api-v1-defaut`, ou baissez celle
du routeur par défaut, pour que `routage.lab.test/v2*` atteigne `api-v2`
tandis que la racine atteint toujours `api-v1`. Restreignez le routeur admin
à `Host(`routage.lab.test`) && PathPrefix(`/admin`)` pour qu'aucun autre nom
d'hôte ne l'atteigne. Qualifiez le service et le middleware du routeur
catalogue vers le provider Docker (`cible@docker`, `marque@docker`). Les
contrôles appellent le véritable point d'entrée HTTP sur le port 80, lisent
le corps de la réponse (`Hostname:`) et les en-têtes, et ajoutent une route
dynamique de plus, sans rapport, pour prouver que rien ne casse.
