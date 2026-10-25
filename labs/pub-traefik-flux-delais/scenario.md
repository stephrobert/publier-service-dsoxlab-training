# Scenario

Traefik on `edge.lab` fronts four backends behind the `api.flux.lab.test`,
`flux.lab.test` and `action.flux.lab.test` hostnames: two interchangeable
API backends load-balanced together, one streaming backend serving a
WebSocket echo and an SSE event feed, and one action backend that
increments a counter on every successful write. Right now the server
transport's forwarding timeouts are so generous that a backend which never
answers at all leaves the client waiting for minutes instead of getting a
clear, bounded failure. The entry point's responding timeout is tuned for
short plain requests and silently kills the WebSocket and SSE connections
after a short idle period, even though both are working exactly as
designed. The load balancer has no health check at all, so a backend that
stops being ready keeps receiving its share of traffic instead of being
taken out of rotation, and healthy backends end up absorbing failures that
were never theirs. Finally, a retry middleware blindly wraps every route,
including the action route: if the backend's response is lost right after
it durably wrote its side effect, Traefik quietly resends the same
request, and the backend counts the action twice.

## Mission

Bound the server transport's forwarding timeouts so a legitimately slow
response still succeeds and a backend that never answers fails within a
few seconds instead of hanging the client. Raise the entry point's
responding timeout enough that an idle WebSocket or SSE connection is not
mistaken for a stalled request, without disabling the protection
entirely. Add a load-balancer health check so an unhealthy backend is
removed from rotation quickly, without ever failing requests meant for its
healthy peer. Finally, remove (or correctly scope) the retry policy on the
action route so a lost response never causes the backend to count the same
business action twice.
