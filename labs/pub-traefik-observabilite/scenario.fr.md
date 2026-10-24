# Scénario

Traefik sur `edge.lab` route déjà `observabilite.lab.test` vers un backend
local géré par systemd. Une instance Prometheus locale fonctionne également,
mais le proxy n'est pas encore observable et l'alerte sur les 5xx manque.

## Mission

Instrumentez le proxy et configurez une alerte utile sans exposer les
endpoints de supervision au réseau.
