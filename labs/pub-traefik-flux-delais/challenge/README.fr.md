# La tâche

Corrigez `/opt/pub-flux/dynamic/routes.yaml` : bornez
`serversTransports.lent.forwardingTimeouts.dialTimeout` et
`.responseHeaderTimeout` à quelques secondes (au lieu de 30 s) pour qu'un
backend mort échoue vite plutôt que de faire attendre ; ajoutez un
`healthCheck` (chemin `/health`, intervalle court) sur le `loadBalancer`
du service `api` pour qu'un backend malsain soit retiré de la rotation au
lieu de continuer à recevoir du trafic ; et retirez (ou cadrez
correctement hors du routeur `action`) le middleware `retry-partout`,
puisque rejouer un POST non idempotent peut dupliquer une action métier
dont seule la réponse a été perdue. Corrigez ensuite
`/opt/pub-flux/traefik-static.yaml` : augmentez
`entryPoints.web.transport.respondingTimeouts.writeTimeout` (3 s
actuellement, trop court pour un flux SSE de plusieurs secondes) à une
valeur généreuse, et redémarrez Traefik
(`docker restart pub-flux-traefik`) puisqu'il s'agit d'un réglage
statique ; le fichier dynamique se recharge automatiquement. Les
contrôles appellent `api.flux.lab.test`, `flux.lab.test` (`/ws`,
`/events`) et `action.flux.lab.test` directement sur le port 80 (noms
déjà résolus dans `/etc/hosts`).
