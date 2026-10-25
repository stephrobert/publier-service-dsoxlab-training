# Scénario

L'application est déjà publiée par HAProxy et une instance Prometheus est
prête à la surveiller. Le point de métriques ne renvoie aucune métrique, et
les deux interfaces de supervision sont joignables depuis d'autres machines.

## Mission

Configurez l'exporteur Prometheus de HAProxy, limitez les deux interfaces de
supervision à l'hôte et faites remonter à Prometheus un scrape réussi ainsi que
la santé du backend.

Le service public doit rester disponible pendant le changement.
