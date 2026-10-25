# Publish two containers behind Traefik

You are on `edge.lab`. In `/opt/pub-lab`, put Traefik in front of two instances
of the `traefik/whoami` web service, reachable as `whoami.lab.test` on port 80.
A third container, `pub-interne`, already runs on the `pub-lab` Docker network
and must stay unreachable through Traefik. `LISEZ-MOI.txt` lists the images
(already pulled, pinned by digest) and the facts the tests rely on.

## Mission

Configure failover and health checks so the service remains usable when an
instance stops or becomes sick:

- when an instance stops, at most one error is tolerated during the first
  5 seconds; afterward, requests must be error-free and must not reach the
  stopped instance for a stable 5-second period;
- when `/health` reports an instance as sick, it must be removed from rotation
  within 5 seconds; requests must remain error-free and the stable 5-second
  period must reach only the other instance;
- after restart or recovery, the instance must receive traffic again within
  40 seconds.
