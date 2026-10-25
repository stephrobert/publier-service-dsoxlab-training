# Scénario

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
