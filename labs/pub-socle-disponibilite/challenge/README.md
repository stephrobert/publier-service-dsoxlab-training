# The task

## The situation

Two identical backend instances run on `edge.lab`, everything on
`127.0.0.1` (the provided probe runs on the same host), behind a single
opaque load balancer. The configuration shipped with three mistakes at
once: the balancer never actually alternates between the two backends as
long as both answer, its health probe interval and failure threshold are
set so high that removing a sick backend would take minutes, and the
recovery threshold is just as slow on the way back.

## Mission

Read `/home/student/README-disp`, then edit
`/etc/pub-disp/politique.yaml` (re-read on every probe and every request,
no restart needed) so that:

- a sample of traffic through the balancer, with both backends healthy,
  actually reaches both of them;
- a backend marked sick (via a flag file, simulating an application
  failure) is removed from rotation within a reasonable window;
- once restored, it comes back into rotation within a reasonable window;
- stopping the balancer itself, the only entry point in this topology,
  proves honestly what a single instance of it cannot survive, while
  each backend remains reachable directly.

Use the provided probe, `/opt/pub-disp/sonder.py`, to observe each of
these from a real HTTP request to the right entry point, not an
assumption about a specific product.

## What is asked

On `edge.lab`, edit `/etc/pub-disp/politique.yaml` so that all four
points below hold. Nothing else needs to be written: the tests observe
the balancer and the backends directly, with the provided probe already
installed there. The policy is re-read on every probe and every request,
no restart needed.

```yaml
repartition:
  actif: <true|false: does the balancer actually alternate between every
    backend it considers healthy, instead of always sticking to the
    first one that answers?>
probe:
  intervalle_s: <how many seconds between two health probes: low enough
    that removing or restoring a backend happens within a window you can
    defend>
  echecs_avant_retrait: <how many consecutive failed probes before a
    healthy backend is removed from rotation: low enough to react, high
    enough not to overreact to a single flaky probe>
  succes_avant_retour: <how many consecutive successful probes before a
    removed backend returns to rotation: same trade-off, on the way
    back>
```

Read `/home/student/README-disp` for the exact ports in this run. Use
the provided probe to check your own work before relying on the tests:

```sh
sudo -u student python3 /opt/pub-disp/sonder.py echantillon <port_repartiteur> <n>
sudo -u student python3 /opt/pub-disp/sonder.py direct <port_backend>
sudo -u student python3 /opt/pub-disp/sonder.py indisponible <port>
```

Simulate an application failure on a backend with
`sudo touch /var/lib/pub-disp/malsain-a` (or `-b`); remove the file to
restore it.

The tests run the same checks themselves, from `edge.lab`, including
stopping the balancer to prove what a single instance of it cannot
survive; they restart it afterward in every case.
