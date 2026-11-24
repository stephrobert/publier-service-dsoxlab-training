# The task

## The situation

Traefik runs on `edge.lab` in front of four backends: a default application, a
v2 API meant to take over under `/v2`, an administration panel that must
answer only on its own hostname, and a catalog discovered through the Docker
provider. Someone wrote explicit priorities without checking which router
should really win, left the administration panel without a hostname
restriction, and referenced the catalog's service and middleware without
qualifying which provider they come from.

## Mission

Fix the router priorities so `/v2` reaches the v2 API instead of the default
application. Restrict the administration panel to its intended hostname: no
other name should reach it. Qualify the catalog's service and middleware
references to the Docker provider. Then prove that adding one more,
unrelated route does not disturb any of the routes you fixed.

## What is asked

Fix `/opt/pub-routage/dynamic/routes.yaml`. The default router must only win
when no more specific rule applies: raise `api-v2`'s priority above
`api-v1-defaut`'s, or lower the default's, so that `routage.lab.test/v2*`
reaches `api-v2` while the root still reaches `api-v1`. Scope the admin
router to `Host(`routage.lab.test`) && PathPrefix(`/admin`)` so no other
hostname reaches it. Qualify the catalog router's service and middleware to
the Docker provider (`cible@docker`, `marque@docker`). The checks call the
real HTTP entrypoint on port 80, read the response body (`Hostname:`) and
headers, and add one more unrelated dynamic route to prove nothing breaks.
