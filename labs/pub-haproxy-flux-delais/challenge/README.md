# Scenario

An API behind HAProxy, with two instances, in-memory sessions, an event
stream and a WebSocket. Four things are wrong.

1. **Every bound has the same value, and there is no queue bound.** A
   connection that never answers, a full queue and a slow response all take
   the same time and return the same signal. An operator therefore cannot say
   which of the three they are looking at, which is exactly what is asked of
   them at three in the morning.

2. **Ten seconds of inactivity, and no tunnel bound.** The event stream dies
   between two heartbeats, and the WebSocket dies in a perfectly normal
   silence. The application's heartbeat is slow on purpose: it is the silence
   between two events that puts an inactivity bound to the test.

3. **The proxy replays everything it can.** A write whose response was lost
   **after** the server processed it is therefore replayed, and the work
   happens twice. The client received nothing: it cannot know.

4. **No session policy.** One request in two changes instance, and the state
   the client believes it has is not there.

The expected bounds are in `/opt/pub-haproxy-flux-delais/recette.txt`. They
are **different from one another**, and that is the point.

## The four checks

1. **Each slow phase has its own bound.** The three injections are played
   separately: an address that does not answer, a server whose single slot is
   taken, and a response slower than its bound. The test measures the three
   **durations** and requires them to be distinct and each to match its bound.
   Three identical durations is one bound disguised as three.

2. **Long streams last the announced duration.** The event stream must return
   several timestamped events spaced by the heartbeat, and the WebSocket must
   still answer after the requested duration, having exchanged nothing in the
   meantime.

3. **The session policy holds, and its limits are stated.** Twenty
   consecutive reads must find the session. Then the test **takes out of
   service** the instance holding it, and checks that the session is lost:
   that is the expected behaviour, not a defect. Pinning a client to an
   instance is not replicating its state, and the dossier must say so.

4. **No write is duplicated.** This check is critical. The write endpoint
   counts the write **then closes without answering**: the work happened, the
   client does not know. After a single attempt, the business counter must be
   exactly one.

   The half that matters comes next: a **read** whose connection fails must
   still succeed. Restricting retries is not removing them, otherwise the
   configuration has lost its fault tolerance in gaining its safety.
