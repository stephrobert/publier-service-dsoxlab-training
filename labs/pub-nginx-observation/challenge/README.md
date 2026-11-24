# Scenario

Nginx publishes the application on `app.lab.test`, and says nothing about
it. The access log uses the default `combined` format: it carries neither
the response time nor the upstream one. Reading it, you cannot tell whether
a slowdown comes from Nginx or from the application. And no status endpoint
is exposed.

## Mission

Expose `stub_status` on `127.0.0.1:8081/nginx_status`, **and on the loopback
interface only**. Replace the application's access log with a **JSON format,
one object per line**, carrying at least `status`, `request_time` and
`upstream_response_time`.

## Observing is not writing fields

A log where `request_time` always read `0.000` would be structured,
parsable, and perfectly useless. The validation therefore confronts every
logged value with a fact it provokes:

- the status endpoint answers locally **and** is refused from the lab
  network address. Exposed to everyone, it hands anybody the service's live
  connection counts;
- every line is **parsed** as JSON, not recognised by the presence of a
  brace: a half-converted log is exactly the state in which a collector
  drops every other line without anyone noticing;
- `/lent` takes **two seconds**, because the backend sleeps two seconds
  there. The logged `request_time` must say so;
- `/casse` answers **503** and `/health` answers **200**: the log must tell
  them apart. A log writing 503 everywhere would satisfy the first half of
  the check and be wrong.

## Hints

- `stub_status` is declared in a `location`, itself inside a `server` whose
  `listen` carries the `127.0.0.1` address.
- `log_format` accepts a JSON literal; remember `escape=json`, without which
  a URL containing a quote breaks the line.
- `$request_time` is the duration seen by Nginx, `$upstream_response_time`
  the application's. Their gap is what names the culprit.
- `docker compose restart` reloads the configuration, and `nginx -t`
  validates it beforehand.
