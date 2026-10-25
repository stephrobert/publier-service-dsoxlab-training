# pub-traefik-flux-delais

**Audience:** the learner.

Tune Traefik's delays and transports so a legitimately slow backend still
succeeds, a persistently stuck backend fails within a bounded time instead
of hanging the client forever, a WebSocket and an SSE stream survive an
idle period instead of being cut by an entry point timeout meant for plain
requests, a sick backend is removed from load-balancing rotation without
dragging healthy backends down with it, and a retry policy never resends
a non-idempotent business action that already succeeded on the backend.

## What you will be able to do

- Configure a server transport's forwarding timeouts so a bounded slowness
  succeeds and a persistent failure still fails quickly, instead of either
  extreme.
- Configure an entry point's responding timeouts so long-lived flows
  (WebSocket, SSE) are not mistaken for a stalled plain HTTP request.
- Configure a load-balancer health check so an unhealthy backend stops
  receiving traffic without failing requests meant for its healthy peers.
- Recognize why a retry middleware applied to a non-idempotent write can
  duplicate a business action, and scope it correctly.

Four backend containers (two interchangeable API backends, one streaming
backend, one action backend with a request counter) and a Traefik
instance are prepared. The task and available paths are described in
`/opt/pub-flux/README`.
