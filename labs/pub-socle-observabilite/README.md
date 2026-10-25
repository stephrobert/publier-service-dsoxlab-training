# pub-socle-observabilite

**Audience:** the learner.

Learn to define what counts as a valid event and a success, tune an alert on
the real failure instead of on noise, correlate one request to its backend
and duration, and tell apart no traffic, lost collection, and a real outage.

## What you will be able to do

- State an SLI's denominator and success criterion explicitly, and check it
  both against a known batch and against live traffic.
- Tune an alert so it fires on an injected outage and clears once it is fixed.
- Relate one request to the backend that served it and the duration observed.
- Write a policy that tells a real failure apart from a mere absence of
  traffic or a collection outage, instead of confusing the three.

Your work happens on `edge.lab`; `challenge/README.md` describes the files to
produce.
