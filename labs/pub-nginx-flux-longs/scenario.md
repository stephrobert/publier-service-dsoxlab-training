# Scenario

Three long-lived transports are published behind Nginx, and all three are
treated like pages: the WebSocket never completes its handshake, SSE events
are held in a buffer, gRPC goes through a plain HTTP proxy, and a
ten-second read timeout cuts every stream mid-conversation.

The bench is described in `/opt/pub-nginx-flux-longs/transports.txt`.

## Mission

Publish the three transports without delaying events or blocking legitimate
exchanges, and release resources when a stream stops.

## What each transport requires, and how they differ

The **WebSocket** needs the handshake forwarded: `proxy_http_version 1.1`,
then the `Upgrade` and `Connection` headers.

**SSE** needs nothing buffered. This is the subtlest trap in the lab,
because a naive test misses it: the six events **do** eventually arrive.
What tells a stream from a batch is the **rhythm**, so the validation
measures the delay of the first event.

**gRPC** needs HTTP/2 and `grpc_pass`, on a dedicated cleartext port. And it
needs an application refusal to stay an application refusal: an
`INVALID_ARGUMENT` reaching the client as `UNAVAILABLE` will make it retry
forever a request that can never succeed.

## What is checked

- the WebSocket handshake completes **and** a frame sent comes back. The
  second half matters: an established connection carrying nothing is the
  hardest version of this defect to diagnose;
- the **first** SSE event arrives in under four seconds, while the backend
  emits six of them one second apart;
- a gRPC call goes through, and the `erreur` payload comes back as an
  application refusal, not a transport failure;
- cutting the backend under an open stream leaves no orphan connection. One
  per client eventually exhausts the proxy, and the symptom appears weeks
  later as "the site is slow".

## Hints

- `proxy_set_header Upgrade $http_upgrade;` and
  `proxy_set_header Connection "upgrade";`, with `proxy_http_version 1.1`.
- `proxy_buffering off;` inside the stream's `location`, not globally: the
  buffer stays useful everywhere else.
- `grpc_pass grpc://...` on a `server` whose `listen` carries `http2`.
- Timeouts are set per route: a long stream does not have a page's needs.
