# La tâche

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
