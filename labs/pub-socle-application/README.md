# pub-socle-application

**Audience:** the learner.

Learn why "it works in curl" is not the same question as "it works in a
browser". A reverse proxy that does not pass on the scheme it actually
terminated, an application that scopes its session cookie to a domain
nobody asked for, a CORS policy that says yes to everyone because saying
no to the right people felt harder, and an identity header still trusted
from the client: each of these is invisible to a tool that does not
enforce same-origin policy, does not store cookies per domain, and does
not follow a redirect chain to its end.

## What you will be able to do

- Read a login journey as a chain of redirects with a scheme, an
  authority and a bounded number of hops, and recognize a loop caused by
  a proxy that silently drops the scheme it actually terminated.
- Scope a session cookie correctly, and verify it the only way that
  matters: by actually using it in a browser, not by reading a response
  header and assuming it will be accepted.
- Tell the difference between an allowed origin and every origin, and
  prove it with a real preflight and a real cross-origin fetch, not a
  curl header that never enforces anything.
- Explain why a reverse proxy must compute an identity from a validated
  session instead of repeating whatever identity header the client
  already sent, and show that a forged header grants nothing once fixed.

Your observations happen on `edge.lab`, using the automated browser
provided there; `challenge/README.md` describes the task precisely.
