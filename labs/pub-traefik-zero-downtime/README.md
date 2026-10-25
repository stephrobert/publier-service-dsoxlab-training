# pub-traefik-zero-downtime

**Audience:** the learner.

Roll a backend version out with bounded errors, remove an unhealthy
candidate and roll back, prove honestly which failure a redundant entry
point actually survives, and fix a certificate rotation tool so two entry
points sharing the same certificate storage never serve a corrupted pair.

## What you will be able to do

- Move live traffic from one backend version to a candidate using a
  weighted Traefik service, instead of an all-or-nothing cutover.
- Add a load-balancer health check so an unhealthy candidate is actually
  removed from rotation, and use it to drive a real rollback.
- Tell apart the failure a redundant entry point survives (losing one of
  several processes) from the failure it does not (losing the single host
  they all run on), and prove both instead of assuming either.
- Recognize why sharing one certificate storage between several entry
  points needs explicit concurrency handling, and fix a tool that lacked
  it.

Two Traefik entry points and two versions of a backend are prepared. The
task and available paths are described in `/opt/pub-zds/README`.

**Honest limit of this lab:** the contract calls for two entry points on
two separate VMs. Only `edge.lab` is available here, so both entry points
actually run on it (see the recipe). This lab turns that limit into the
lesson for the "edge" point, instead of hiding it: it asks you to prove,
and to declare in writing, which failure survives and which does not,
rather than to claim a host-level resilience this single-VM setup cannot
provide.
