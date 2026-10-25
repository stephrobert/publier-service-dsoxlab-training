# pub-traefik-routage

**Audience:** the learner.

Resolve a web of partially colliding Traefik routes: explicit priorities that
fight each other, a sensitive application reachable from the wrong hostname,
and a cross-provider reference left unqualified.

## What you will be able to do

- Set explicit router priorities that reflect the intended specificity.
- Scope a sensitive route to the hostname that must serve it.
- Qualify a service and a middleware reference across providers.
- Verify that adding an unrelated route does not break existing ones.

Four backends and a partially miswired Traefik are prepared. The task and
available paths are described in `/opt/pub-routage/README`.
