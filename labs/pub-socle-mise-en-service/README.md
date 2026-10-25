# pub-socle-mise-en-service

**Audience:** the learner.

Reception is where a release stops being yours and becomes the client's
problem: once it is accepted, "it does not work" is your incident, not a
retest. This lab makes you play both sides of that handover on the same
release, `service.mes.test`, published in TLS on `edge.lab`.

## What you will be able to do

- Write and run an acceptance matrix from an independent client (`poste.lab`):
  DNS, TLS, the business route, and the forbidden route, without bypassing
  DNS resolution for the DNS check itself.
- Restore active configuration and state from a backup after losing both,
  and prove the restored service answers with the real business value, not a
  default.
- Roll a release back to a known-good origin after a bad switch, accounting
  for a cache that does not forget a stale decision on its own.
- State, in writing, which parts of this acceptance were only simulated and
  which proofs a real Internet-facing release would still need.

