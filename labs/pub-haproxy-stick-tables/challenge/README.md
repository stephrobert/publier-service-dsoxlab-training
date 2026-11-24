# Scenario

A stick-table is already in place, in a backend that serves nothing else. It
fills up, it reads fine, and it protects nothing. Three things are wrong:

1. **The tracked key is a header the client sends.** Everyone therefore picks
   their own counter, and changing it is enough to start from zero. See for
   yourself:

   ```bash
   for v in un deux trois; do curl -s -o /dev/null -H "X-Client-Id: $v" http://127.0.0.1/; done
   echo 'show table compteurs' | sudo socat -t2 stdio /run/haproxy/admin.sock
   ```

2. **The threshold is never reached.** The deny rule exists, it is correct,
   and it never fires.

3. **The window and the expiry are the same number.** They are two different
   bounds: one says over how long the rate is measured, the other how long an
   entry survives its last request. Conflating them is the most common way of
   believing you measure a rate when you measure a lifetime.

What the table must count, with its bounds and threshold, is written in
`/opt/pub-haproxy-stick-tables/recette.txt`.

## The four checks

1. **The table counts the right object, over the right window.** The test
   sends a known number of requests from the client and reads the counters
   through the socket: the key must be **the client's address**, and the rate
   must equal what was sent. Then it waits out the window and requires the
   rate to fall back to zero, which measures the window rather than the count.

2. **Overrun refuses, and only overrun.** A burst of `seuil` requests must
   **pass**: a control stricter than what was asked is also a fault. Beyond
   it, the refusal is a 429, and it is reproducible. During that refusal
   **another source** must keep being served, otherwise the limit does not
   protect the service, it replaces it.

3. **The key cannot be chosen by the client.** This check is critical. Once
   the source is blocked, the test replays the request with five different
   header values: all must stay refused.

   The half that matters comes next: after the window, the same source must
   **get the service back**. A block that never lifts is not a rate limit, it
   is a ban, and that is not what the recipe asks for.

4. **The memory bounds are the declared ones.** The declared size is read
   from the table, and the expiry is measured for real: after it, the entry
   must have **disappeared** from the table, not merely fallen back to zero.
   That is the difference between the two bounds, seen from the other side.

   A dossier completes this check, read by a human: it must say what this
   table **does not protect**. At least two limits are expected, and they are
   not guessable from reading the configuration.
