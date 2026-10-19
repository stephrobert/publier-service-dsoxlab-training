# Challenge: two instances, one entry point, no visible failure

You work in `/opt/pub-lab` on `edge.lab`.

## What is expected

1. Traefik answers on port 80 of the machine, and `whoami.lab.test` (sent as the
   `Host` header) reaches the two `traefik/whoami` instances, which share the
   load.
2. Traefik exposes nothing by default: a container that carries no opt-in label
   (`pub-interne`) answers 404 through it.
3. No backend publishes a port on the host.
4. While one instance is stopped, a client sending requests in a loop receives
   no error. When it comes back, it takes traffic again.
5. An instance that keeps running but reports itself unhealthy on `/health` stops
   receiving traffic, with no error either.

## What is proven

The tests send requests as a client would, stop and sicken an instance
themselves, then restore it. They read what the machine publishes, never your
Compose file.
