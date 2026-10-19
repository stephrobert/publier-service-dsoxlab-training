# Publish two containers behind Traefik

You are on `edge.lab`. In `/opt/pub-lab`, put Traefik in front of two instances
of the `traefik/whoami` web service, reachable as `whoami.lab.test` on port 80.
A third container, `pub-interne`, already runs on the `pub-lab` Docker network
and must stay unreachable through Traefik. `LISEZ-MOI.txt` lists the images
(already pulled, pinned by digest) and the facts the tests rely on.

## Mission

A client must be able to use the service while one of its two instances is
stopped or sick, without ever receiving an error.
