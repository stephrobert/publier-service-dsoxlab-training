# Scenario

An API is published behind Nginx, with limits already in place, and placed
wrongly: one request per minute, a single zone shared by every route, and
`set_real_ip_from 0.0.0.0/0`, which makes Nginx believe any caller's
`X-Forwarded-For`.

The policy to apply is in `/opt/pub-nginx-limites/politique.txt`.

## Mission

Apply the policy: the announced rate and burst per route, a body limit, a
**429** refusal, and a grouping key that cannot be forged.

## The central trap: what serves as the key

Grouping by IP address is the reflex, and it is wrong here. The users are
**behind a NAT**: they share one address, so one caller's abuse refuses
them all.

But grouping by a header the caller chooses is **worse**: changing it on
every request is enough never to be counted.

The policy settles it: the API key distinguishes clients, and the
`X-Forwarded-For` is only believed from the declared upstream proxy,
`127.0.0.1`. The validation measures **both sides** of that trade-off: a
forged address does not escape the limit, and another key does not inherit
the penalty.

## What is checked

- fifteen requests in a row on `/public` go through, since the policy allows
  a burst of twenty. A limit that refuses normal traffic is a self-inflicted
  outage;
- abuse receives a **429**, not the 503 Nginx returns by default. A 503
  reads as an outage and invites a harder retry; 429 is the only answer that
  asks the caller to slow down;
- **critical**: changing the `X-Forwarded-For` on every request does not
  escape the limit, and another API key is not penalised for it;
- hammering `/admin` does not close `/public`.

## Hints

- `limit_req_zone` declares a zone and its key, `limit_req` applies it.
  Several zones can coexist, and that is what separates the routes.
- `limit_req_status 429;` changes the refusal code.
- `set_real_ip_from` lists the addresses whose `X-Forwarded-For` is
  believed. The rest of the world is not.
- `client_max_body_size` bounds the body, and is declared per `server` or
  per `location`.
