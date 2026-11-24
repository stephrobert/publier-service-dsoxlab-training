# The task

## The situation

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

## What is asked

Fix `/opt/pub-modele/dynamic/routes.yaml` so that `modele-a.lab.test` reaches
backend `app-a`, and `modele-b.lab.test` reaches the Docker-provider service
named `cible` (not the file-provider decoy of the same name). Remove whatever
makes an unplanned hostname answer with an application. The check calls the
real HTTP entrypoint on port 80 and reads the response body.
