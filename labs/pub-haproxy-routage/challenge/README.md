# Scenario

HAProxy is running, four backends are healthy, and the routing table is
wrong. The four faults are of the same family, and that is the subject of the
lab: **none of the four lines is wrong on its own.**

1. The line that consults the name table sits **before** the path exceptions.
   HAProxy keeps the first matching rule, so the exceptions are written,
   readable, correct, and never reached.
2. `path_beg /panier` also catches `/panierarchive` and `/panier-public`. A
   prefix is not a path.
3. `/api/v2/` is routed to the API, which does not serve it: the route makes
   it answer as if it existed.
4. `default_backend panier` makes the cart the destination of every
   unexpected name, including the ones a third party chooses.

The table to obtain is written in `/opt/pub-haproxy-routage/recette.txt`. It
says what must happen, never with which directives to obtain it.

## What measures, and why it is not the answer returned

Each backend **counts the requests it serves** and reports that on the
loopback. The validation reads those counters before and after every request.

This is necessary: a leaking route is invisible in the answer. A
`default_backend panier` returns 200, with a plausible body, for any name.
Only the backend can say it served that request, and neither the
configuration nor the client can say it in its place.

## The four checks

1. **Every name and path combination reaches the intended backend.** The
   matrix carries neighbouring paths deliberately, and every request is
   counted at the expected backend, and only there.

2. **An unexpected name reaches no backend.** This check is critical, and it
   is measured on the counters: refusing with a 404 while having reached a
   backend does not count.

   Note what it does not say: an unexpected **path** under a known name is
   not refused. The table gives each name a default route, and that is what
   applies. It is the **names** that have no default route, and `/api/v2/`,
   which is refused by name.

3. **The table changes at runtime, and does not survive a reload.** The
   validation changes one entry through the runtime socket, checks that
   routing follows, reloads, then checks that routing has **come back** to
   what the file says. Both halves matter: the first proves the map really
   decides, instead of being decorative next to ACLs that actually rule; the
   second is why a runtime change is always copied back into the file.

4. **A dossier explains the order of decisions.** A human reads it, and its
   reasoning is not graded. The test only checks that it exists and covers the
   two cases that cannot be settled without looking: the paths neighbouring
   `/panier`, and `/api/v2/`.
