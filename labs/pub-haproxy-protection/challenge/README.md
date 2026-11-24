# Scenario

HAProxy already publishes the application on `app.lab.test`, and protects it
in no way: no security header, `/admin` served to whoever asks, no rate
limit at all, and write methods forwarded to the backend although the
application never uses them.

## Mission

Add the security headers, require the `labadmin` / `Lab-Admin-Only`
credentials on `/admin`, refuse with **429** any rate above **20 requests
per 10 seconds per source address**, and reject `DELETE` and `PUT`. All of
it without breaking the application's normal requests.

## What is checked, and why in both directions

A refusal is only proven by showing what still goes through. A configuration
that rejected everything would satisfy "`/admin` answers 401", "the
excessive rate is refused" and "`DELETE` is refused" in one go, having
simply removed the service. Every check therefore carries its
counter-example:

- the four headers are present **on an answer that came from the backend**,
  not on an HAProxy error page;
- `/admin` answers **401** to an anonymous caller **and** serves the backend
  with the supplied credentials;
- a burst of 40 requests meets **both 429s and 200s**: only 429s would mean
  a closed door, only 200s no limit at all. And the service becomes
  available again once the window has passed, because a rate limit
  **releases** instead of banning;
- `DELETE` and `PUT` are refused **and** `GET` still reaches the backend.

## Hints

- A per-source rate limit is built with an `ip` `stick-table` carrying an
  `http_req_rate`, and an `http-request deny deny_status 429` above the
  threshold.
- Authentication is declared in a `userlist`, and required with
  `http-request auth` when `http_auth` is not satisfied.
- `http-response set-header` sets a header on the answer; doing it in the
  `frontend` sets it for everything it serves.
- `docker compose restart` is enough to reload the configuration, and
  `haproxy -c -f` validates it before you put it in place.
