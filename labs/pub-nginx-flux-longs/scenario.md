# Scenario

Three long-lived transports are published behind Nginx, and all three are
treated like pages: the WebSocket never completes its handshake, SSE events
are held in a buffer, gRPC goes through a plain HTTP proxy, and a
ten-second read timeout cuts every stream mid-conversation.

The bench is described in `/opt/pub-nginx-flux-longs/transports.txt`.

## Mission

Publish the three transports without delaying events or blocking legitimate
exchanges, and keep a conversation alive while it has nothing to say.

## What each transport requires, and how they differ

The **WebSocket** needs the handshake forwarded: the `Upgrade` and
`Connection` headers, over an HTTP/1.1 connection to the backend. That
version has been the default since nginx 1.29.7, so only the headers are
missing here.

**SSE** needs nothing buffered. This is the subtlest trap in the lab,
because a naive test misses it: the six events **do** eventually arrive.
What tells a stream from a batch is the **rhythm**, so the validation
measures the delay of the first event.

**gRPC** needs HTTP/2 and `grpc_pass`, on a dedicated cleartext port. And it
needs an application refusal to stay an application refusal: an
`INVALID_ARGUMENT` reaching the client as `UNAVAILABLE` will make it retry
forever a request that can never succeed.

All three, finally, need **time**. The starting configuration cuts any
route whose backend has said nothing for ten seconds, which is exactly what
a long stream does: it goes quiet. `proxy_read_timeout` counts the time
**between two reads**, not the lifetime of the stream.

## What is checked

- the WebSocket handshake completes **and** a frame sent comes back. The
  second half matters: an established connection carrying nothing is the
  hardest version of this defect to diagnose;
- the **first** SSE event arrives in under four seconds, while the backend
  emits six of them one second apart;
- a gRPC call goes through, and the `erreur` payload comes back as an
  application refusal, not a transport failure;
- a WebSocket conversation that stays silent for fifteen seconds
  **survives**, and resumes afterwards. Silence is what cuts, not duration:
  a chatty stream never triggers this timeout, and the defect only shows up
  in production, on the conversation that had nothing to say for a
  minute.

## Hints

- `proxy_set_header Upgrade $http_upgrade;` and `proxy_set_header Connection`.
  A hard-coded `"upgrade"` is fine on a dedicated route such as `/ws`; as soon
  as the route also carries ordinary traffic, compute it with a `map` on
  `$http_upgrade`, or every request through that `location` asks for a
  protocol switch. `proxy_http_version` is not what is missing: 1.1 has been
  the default since nginx 1.29.7. Writing it does no harm, and even carries
  the configuration to an older nginx, but it repairs nothing here.
- `proxy_buffering off;` inside the stream's `location`, not globally: the
  buffer stays useful everywhere else.
- `grpc_pass grpc://...` on a `server` whose `listen` carries `http2`.
- Timeouts are set per route: a long stream does not have a page's needs.
