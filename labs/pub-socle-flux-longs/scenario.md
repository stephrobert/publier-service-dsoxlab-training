# Scenario

A notification service runs on `edge.lab`, everything on `127.0.0.1` (the
measuring client runs on the same host). It exposes a WebSocket (an echo
endpoint) and a Server-Sent Events stream fed by a small producer
service, which emits one notification per second as long as it runs. The
configuration shipped with four mistakes at once: every WebSocket echo is
delayed by three seconds, the SSE stream buffers fifty events before
sending any of them, the heartbeat interval is set so high it never
actually fires, and a producer failure leaves the SSE stream open and
silent forever instead of signaling it.

## Mission

Read `/home/student/README-flux`, then edit `/etc/pub-flux/politique.yaml`
(re-read on every message and every loop of a stream, no restart needed)
so that:

- a WebSocket message comes back as an echo in under a second;
- SSE data events arrive one at a time as they are produced, not bunched
  together;
- the SSE stream emits a heartbeat within a few seconds, not thousands;
- when the producer is stopped, the SSE stream sends a dedicated failure
  event and then closes, instead of hanging silently.

Use the provided measuring client, `/opt/pub-flux/mesure_flux.py`, to
observe each of these by timing arrival, not by reading a final body.
