# The task

Fix `/opt/pub-flux/dynamic/routes.yaml`: bound
`serversTransports.lent.forwardingTimeouts.dialTimeout` and
`.responseHeaderTimeout` to a few seconds (instead of 30s) so a dead
backend fails fast instead of hanging; add a `healthCheck` (path
`/health`, a short interval) on the `api` service's `loadBalancer` so an
unhealthy backend is removed from rotation instead of still receiving
traffic; and remove (or correctly scope away from the `action` router) the
`retry-partout` middleware, since retrying a non-idempotent POST can
duplicate a business action whose response was merely lost. Then fix
`/opt/pub-flux/traefik-static.yaml`: raise
`entryPoints.web.transport.respondingTimeouts.writeTimeout` (currently 3s,
too short for a multi-second SSE stream) to a generous value, and restart
Traefik (`docker restart pub-flux-traefik`) since this is a static setting;
the dynamic file is reloaded automatically. The checks call
`api.flux.lab.test`, `flux.lab.test` (`/ws`, `/events`) and
`action.flux.lab.test` directly on port 80 (names already resolved in
`/etc/hosts`).
