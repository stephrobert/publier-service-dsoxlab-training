# Scenario

A catalogue is published behind Nginx with caching already in place, and in
place wrongly. Four defects coexist, and the first one explains almost all
the others:

- `proxy_ignore_headers Cache-Control Expires Set-Cookie`: the contract the
  origin states on each of its responses is thrown away;
- `proxy_cache_key "$uri"`: the key sees neither the requested language, nor
  the session, nor the query string;
- `proxy_cache_valid 200 10m` applied to everything, with no distinction
  between a stable page and a stock state that moves;
- `add_header X-Cache-Status "HIT" always`, which announces HIT on **every**
  response, including the ones that just came through the origin.

The content contract is in `/opt/pub-nginx-cache/contrat-de-contenu.txt`.

## Mission

Apply that contract: eligible public responses really are served from cache,
representation variants do not get mixed up, no private response ever
crosses from one account to another, and volatile content stays fresh.

## What the validation never reads: `X-Cache-Status`

A cache is usually checked by reading that header. It is a **statement**
made by Nginx, not a measurement, and Nginx is the thing under test. The
fourth defect is there to show it: it prints HIT on a MISS, and any check
that believed it would report green on a cache that does not exist.

The measurement is therefore taken at the origin, on the VM's loopback,
where Nginx has no say: the application counts its **body generations**. A
HIT then becomes a fact, a response served without the origin producing
anything. A `304` does not count as a generation, so that a revalidation
policy passes the measure just as a short TTL does.

## What is verified

- a second request for the public home page makes the origin produce
  **nothing**;
- an English request does not receive the French copy, and the French
  variant is still served from cache. Both sides count: separating the
  variants by giving up caching them does not answer the contract;
- **critical**: the alpha account's randomly drawn marker never reaches the
  beta account nor an anonymous request, and the public page is still
  cached. Removing the cache is not fixing it;
- seven seconds after the origin changes, `/catalogue/stock` carries the new
  value, and two back-to-back requests do not make it produce two bodies.

The validation paths carry a token unique to each measurement, which the
origin ignores and which designates the same resource: every measurement
therefore starts from a cold cache entry, whatever key you choose.

## Hints

- `proxy_cache_valid` only applies if the origin's `Cache-Control` is not
  ignored. Removing a directive is sometimes the whole fix.
- Nginx has honoured `Vary` since 1.7.7: an origin announcing
  `Vary: Accept-Language` is enough to keep variants apart, without touching
  the key.
- `proxy_no_cache` and `proxy_cache_bypass` decide not to **store** and not
  to **serve** from cache, and both are declared separately.
- `proxy_cache_revalidate on` revalidates a stale entry with its `ETag`
  instead of regenerating it.
- `add_header X-Cache-Status $upstream_cache_status;` gives you a header
  that tells the truth. It is not graded, but it is what makes a cache
  observable.
