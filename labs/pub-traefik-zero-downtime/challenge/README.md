# The task

Edit `/opt/pub-zds/dynamic/routes.yaml` (watched by both entry points):
replace the single hard-coded `app` service (one server, `v1` only) with a
`loadBalancer` service that lists **both** backends as servers
(`http://pub-zds-app-v1:8080` and `http://pub-zds-app-v2:8080`, each with
an explicit `weight`), and add a `loadBalancer.healthCheck` (path
`/health`, a short interval such as `2s`) that applies to every server of
that service. Traefik's `weighted` *service* type (combining two named
sub-services) **can** take an unhealthy sub-service out, but only when it
carries a `healthCheck` of its own, and under three conditions: it must
be enabled, every descendant must have one or service creation fails, and
it is only defined with the file provider. Without that `healthCheck`,
nothing is wired and the unhealthy child stays in rotation.

This lab therefore asks for the simplest form, which depends on none of
those conditions: **two servers of a single load-balanced service**,
whose health checks remove one server at a time from the rotation. Adjust the weights to move traffic from `v1` to `v2`,
observe the live mix and error rate with real HTTP requests, then remove
`/app/healthy` from `pub-zds-app-v2` (`docker exec pub-zds-app-v2 rm
/app/healthy`) and confirm traffic falls back to `v1` on its own; restore
`v2`'s health afterward with `docker exec pub-zds-app-v2 touch
/app/healthy`.

From `poste.lab`, curl `https://zds.lab.test:<port>/` (ports in
`/opt/pub-zds/ports.env`) against each entry point, stop
`pub-zds-entry-a` and confirm `pub-zds-entry-b` still answers, then
restart `pub-zds-entry-a`. To observe the host-level failure, block both
ports at once on `edge.lab` before Docker's NAT rewrites them (for
example with `iptables -t raw -I PREROUTING -p tcp --dport <port> -j
DROP` for each, since a plain `-I INPUT` rule does not see traffic
Docker has already redirected to a container) and confirm both entry
points become unreachable from `poste.lab`; remove the rule afterward.
Write your conclusion in `/home/student/domaine-de-panne.yaml` with keys
`perte_processus` and `perte_hote`, each set to `survit` or
`ne_survit_pas`.

Fix `/opt/pub-zds/outils/tourner-certificat.sh` so a concurrent, repeated
invocation from two callers never leaves `/opt/pub-zds/tls/tls.crt` and
`tls.key` mismatched or truncated: write to a temporary path and rename
both files into place atomically (or serialize with a lock), so every
observer always sees either the old complete pair or the new complete
pair, never a mix. Restart both Traefik containers after a rotation if
needed (the file provider reloads routes on change, but the default
certificate referenced by `tls:` is read when a connection needing it is
negotiated, which is normally enough; restarting is a safe fallback if a
test still sees a stale handshake).
