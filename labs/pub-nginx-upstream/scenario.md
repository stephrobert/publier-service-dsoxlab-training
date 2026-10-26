# Scenario

Two identifiable backends serve the same application behind Nginx. Load
sharing works, and it has two defects: `max_fails=0` **disables** passive
detection, and `proxy_next_upstream` carries `non_idempotent`, which allows
a `POST` to be replayed.

The bench and its controls are described in
`/opt/pub-nginx-upstream/banc.txt`.

## Mission

Share traffic between both backends, give passive detection thresholds you
can justify, and fix the retry policy.

## What the open source build can do, and what it cannot

Open source Nginx has **no active probe**: it will never query a backend to
find out whether it is healthy. The only detection available is passive,
through `max_fails` and `fail_timeout`, and it learns from the clients'
own requests.

A direct consequence, and the point of the lab: **the first errors are
served** before the backend is removed. The validation therefore measures
that errors **stop**, not that there never were any. Demanding zero errors
would demand of this tool what it cannot do, and would push you to write a
configuration that lies.

## What is checked

- both backends receive traffic while healthy;
- a backend put into error **stops** receiving traffic: the measurement
  covers the second half of a thirty-request burst;
- once healthy again, it **comes back** into rotation. A permanent removal
  is not detection, it is deletion;
- **critical**: an order sent is never counted twice. The bench backend
  increments the counter **before** knowing whether it will answer: in error
  mode it has therefore written and then failed, which is exactly the
  situation where a retry duplicates the action. The counter is the only
  witness, since the client receives an error either way.

## Hints

- `max_fails` and `fail_timeout` are declared on the `upstream`'s `server`
  line. `max_fails=0` means "never remove".
- `fail_timeout` serves twice: it is the window during which failures are
  counted, and the delay after which the backend is tried again.
- `proxy_next_upstream` decides what gets replayed. Its default does not
  replay non-idempotent requests, and `non_idempotent` lifts precisely that
  protection.
