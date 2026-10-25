# Scenario

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
