# pub-socle-flux-longs

**Audience:** the learner.

Learn why a stream is not a request: a body that never comes until the
end, an event that arrives bunched with nine others, a connection that
goes quiet without ever confirming it is still alive, a backend that
disappears without a word. None of this is visible to a tool that reads
a response once it is complete, because a stream's entire point is that
it never completes until you stop asking.

## What you will be able to do

- Time a WebSocket round trip after the handshake and recognize when an
  artificial delay, not the network, is the cause of a slow echo.
- Read Server-Sent Events as they arrive, one at a time, and tell a
  buffering policy that holds events back from one that forwards them as
  soon as they exist.
- Choose a heartbeat interval that actually fires often enough for a
  client to trust a quiet stream is still alive, instead of one so long
  it might as well not exist.
- Make a backend failure explicit on the stream it feeds, with a
  dedicated event and a clean close, instead of leaving the client to
  wait on a connection nobody will ever answer again.

Your observations happen on `edge.lab`, using the provided measuring
client; `challenge/README.md` describes the task precisely.
