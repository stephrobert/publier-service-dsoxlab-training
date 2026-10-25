# Scenario

Traefik runs on `edge.lab` in front of two backends: `app-a`, reachable only
through the file provider, and `app-b`, discovered through the Docker
provider under the service name `cible`. Someone wired the dynamic
configuration in a hurry: `modele-a.lab.test` and `modele-b.lab.test` both
point at the same unreachable service, and a leftover catch-all router answers
every hostname with `app-a`, including ones nobody asked for.

## Mission

Fix the dynamic configuration so that `modele-a.lab.test` reaches `app-a` and
`modele-b.lab.test` reaches `app-b` through its Docker-provider service,
correctly qualified. Remove whatever makes an unplanned hostname answer with
an application; it must reach none.
