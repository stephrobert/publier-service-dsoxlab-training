# Challenge: two instances and measurable failover

You work in `/opt/pub-lab` on `edge.lab`.

## What is expected

1. Traefik answers on port 80 of the machine, and `whoami.lab.test` (sent as the
   `Host` header) reaches the two `traefik/whoami` instances, which share the
   load.
2. Traefik exposes nothing by default: a container that carries no opt-in label
   (`pub-interne`) answers 404 through it.
3. No backend publishes a port on the host.
4. When an instance stops, at most one error is tolerated during the first
   5 seconds. After that, requests must be error-free and must not reach that
   instance for a stable 5-second period. It receives traffic again within
   40 seconds of restart.
5. An instance reporting itself unhealthy on `/health` is removed from rotation
   within 5 seconds. Requests remain error-free; during the following stable
   5-second period, only the other backend receives traffic. The instance
   receives traffic again within 40 seconds of recovery.

## What is proven

The tests send requests as a client would, stop and sicken an instance
themselves, then restore it. They read what the machine publishes, never your
Compose file.
