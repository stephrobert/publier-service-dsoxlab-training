# Scenario

Two identifiable backends serve the same application behind Nginx, and the
given configuration carries **three** defects: the second backend is
declared `backup`, so it only serves when the first one fails; `max_fails=0`
**disables** passive detection; and `proxy_next_upstream` carries
`non_idempotent`, which allows a `POST` to be replayed.

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

A direct consequence, and the point of the lab: **the first requests do go
to the faulty backend** before it is removed. The validation therefore
measures that it **stops** receiving any, not that it never received one.
Demanding zero faulty requests would demand of this tool what it cannot do,
and would push you to write a configuration that lies.

## What is checked

- both backends receive traffic while healthy;
- a backend put into error **stops being solicited**. The measurement is
  taken **on the backend**, in `vus-a.txt`, not at the client: the retry
  catches the 502 on the other backend, so the client gets a 200 whether a
  removal happened or not. Counting the client's errors would measure the
  retry, not the detection;
- once healthy again, it **comes back** into rotation. The check first
  requires that it was **removed**: where nothing is ever removed, "it came
  back" is true without anything having happened. A permanent removal is not
  detection, it is deletion;
- **critical**: an order sent is never counted twice. The bench backend
  increments the counter **before** knowing whether it will answer: in error
  mode it has therefore written and then failed, which is exactly the
  situation where a retry duplicates the action. The counter is the only
  witness, since the client receives an error either way.

## Hints

- `max_fails` and `fail_timeout` are declared on the `upstream`'s `server`
  line. `max_fails=0` means "never remove", and `backup` on that same line
  means "only serve if the first one fails".
- `fail_timeout` serves twice: it is the window during which failures are
  counted, and the delay after which the backend is tried again.
- `proxy_next_upstream` decides what gets replayed. Its default does not
  replay non-idempotent requests, and `non_idempotent` lifts precisely that
  protection.
