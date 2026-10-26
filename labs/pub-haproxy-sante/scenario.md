# Scenario

Two backends serve the same application behind HAProxy. They have equal
weights and **nobody watches them**: no `option httpchk`, no `check`, no
declared weights. A backend that falls therefore stays in the rotation.

See it for yourself before writing anything:

```bash
echo casse > /opt/pub-haproxy-sante/etat-beta
for i in $(seq 6); do curl -s -o /dev/null -w '%{http_code} ' http://127.0.0.1/; done
echo pret > /opt/pub-haproxy-sante/etat-beta
```

Each backend exposes `/ready`, and its state is driven by a file you own. The
`casse` state degrades both: the probe returns 503 **and** real requests
return 500. This is the situation a readiness probe exists to cover, that of a
live service whose dependency has fallen.

Weights and thresholds are prescribed in
`/opt/pub-haproxy-sante/recette.txt`. They are not left to you because the
validation measures **windows**: a removal must happen, and a dip shorter than
the threshold must not cause one. Without known thresholds those two
measurements would have no reference.

## Mission

Declare the probe and its thresholds, the weights, and show that you can take
a backend out of service without cutting what it already serves.

## The four checks

1. **When healthy, each takes the share its weight gives it.** Measured on a
   sample, and confirmed by the stats table: the test requires the probe to be
   **layer 7** (`L7OK`), not a mere connection opening. A bare `check` verifies
   that a port accepts, which a service that has lost its database also does.

2. **A live backend whose readiness fails is removed.** The window is computed
   from the recipe's thresholds, and the test reads HAProxy's own transition
   counter: it requires **one** down transition, not a state. After
   convergence, no error must reach the client any more.

3. **A dip shorter than the threshold removes nothing.** This is the
   counter-test, and it is the half that matters: a probe tuned too short turns
   every hiccup into a switchover, and the switchover costs more than the
   hiccup. The test requires that probes **failed** and that no down transition
   happened. Without this second half, `fall 1` would pass check 2 easily.

4. **Draining stops new assignments without cutting the established one.** A
   long flow is opened on the target server, then the server is drained. New
   requests must no longer reach it, and the flow must continue to its end.
   That is the difference between draining and stopping, and it is what makes
   maintenance possible without a visible outage.
