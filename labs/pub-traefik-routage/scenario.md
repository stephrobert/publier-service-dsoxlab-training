# Scenario

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
