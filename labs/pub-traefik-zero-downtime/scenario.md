# Scenario

`zds.lab.test` is served by two twin Traefik entry points on `edge.lab`
(ports read from `/opt/pub-zds/ports.env`), both watching the exact same
dynamic configuration and serving the exact same certificate. Production
traffic is hard-coded onto backend `v1`; a candidate `v2` is already
running, healthy, and reachable on the Docker network, but nothing in the
current configuration can move traffic to it gradually, and nothing
removes a backend from rotation if it stops answering correctly: the
load-balanced service has no health check. A certificate rotation tool,
`/opt/pub-zds/outils/tourner-certificat.sh`, is shared by both entry
points; it was written assuming it only ever runs once at a time, which is
not a safe assumption for a tool meant to serve two independent entry
points.

## Mission

Read `/opt/pub-zds/README`, then:

- Build a real, gradual path from `v1` to `v2` (two weighted servers of
  the same load-balanced Traefik service, not a `weighted`
  *service* combining two separate sub-services, which does not
  redistribute traffic away from an unhealthy sub-service in Traefik v3)
  and show traffic moving through both versions during the
  transition, with a bounded share of errors.
- Add a load-balancer health check on the backend service so that, when
  `v2` is marked unhealthy (its `/app/healthy` marker removed, simulating
  a real failure), it is actually removed from rotation and traffic falls
  back to `v1` without a human editing anything by hand.
- From `poste.lab`, observe what happens when one entry point's process is
  stopped (the other must keep serving), and what happens when the single
  host carrying both entry points becomes unreachable (both necessarily
  stop, because they share one failure domain). Write your conclusion,
  for each of the two failures, as `survit` or `ne_survit_pas`, in
  `/home/student/domaine-de-panne.yaml`:

  ```yaml
  perte_processus: survit
  perte_hote: ne_survit_pas
  ```

  Do not guess: trigger each failure for real and observe the client's
  view before writing the file. Claiming a resilience this single-VM lab
  does not have is worse than admitting its limit.
- Fix `/opt/pub-zds/outils/tourner-certificat.sh` so that running it twice
  at the same time from both entry points never leaves a mismatched or
  unreadable certificate/key pair in the shared storage; both entry points
  must keep serving valid TLS afterward.
