# Scenario

A gateway caches, retries failed requests and waits for the backend,
following `/opt/pub-socle-cache-delais/politique-cache.yaml`. That policy
was written for speed, and it delivers it.

It also has four defects, one per check: it caches `/prive`, it varies on
nothing, it retries `POST`, and it waits ten minutes for a dead backend.

The bench identities and routes are in
`/home/student/identites-cache.txt`.

## Mission

Fix the policy. The cache must keep speeding up what can be sped up,
without ever serving one user's data to another, without duplicating an
order, and without leaving a caller waiting forever.

## The two traps, and why they are invisible

**Variation.** Caching `/public` without varying on the language serves the
French answer to whoever asks in English. Caching a private route under a
key that does not distinguish the user serves Alice's data to Bob. In both
cases the service is faster and the cache looks like it works.

**Retries.** The application increments its business counter **and then**
drops the connection without answering. The caller therefore cannot tell
"the action never happened" from "the action happened, the answer was
lost". Retrying in doubt duplicates the order, and **only the counter
knows**: the client sees exactly the same thing either way.

That is why the decision to retry is taken on the **method**, never on what
you observe.

## What is checked

- an eligible answer is **reused**, and its variation respected. `/public`
  carries a number drawn at random on every pass: two identical answers
  prove a cache, two different ones prove there is none. No header is taken
  on trust;
- **critical**: Bob never receives Alice's data, nor the other way round;
- **critical**: an order sent once is counted **once**;
- the legitimate two-second slowness goes through, and the outage is
  bounded. Both halves count: a bound that rejects what works is a
  self-inflicted outage.

## Hints

- The gateway re-reads the policy on every request.
- `cache.varier_sur` lists the headers that distinguish two entries. A
  header absent from that list distinguishes nothing.
- A private route has two remedies, and the safest is the simplest.
- `delais.lecture` is chosen by measuring the slowest legitimate answer, not
  by picking a round number.
