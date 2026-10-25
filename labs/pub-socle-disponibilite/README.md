# pub-socle-disponibilite

**Audience:** the learner.

Learn why "it has two instances" is not the same claim as "it survives
losing one of them". A load balancer that never actually spreads traffic
across both healthy backends, a health probe so slow and tolerant it
would take minutes to notice a real outage, and the same blind spot on
the way back: none of this shows up by reading a configuration file, only
by actually breaking something and timing what happens next.

## What you will be able to do

- Prove, by sampling real traffic, that a load balancer actually spreads
  requests across every backend it considers healthy, instead of sticking
  to the first one that answers.
- Choose a probe interval and a failure threshold that remove a sick
  backend within a window you can actually defend, instead of one so slow
  it is indistinguishable from never.
- Choose a recovery threshold that brings a healthy backend back without
  waiting forever, while still being high enough to resist a single
  flaky probe.
- State, honestly and from a real measurement, what a single load
  balancer instance cannot survive: itself going down.

Your observations happen on `edge.lab`, using the provided probe;
`challenge/README.md` describes the task precisely.
