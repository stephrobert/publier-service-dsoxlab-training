# Issue and renew a HAProxy certificate

## The situation

A small application is available on the host, but the supplied HAProxy
deployment does not provide HTTPS correctly. The test ACME authority Pebble
and its HTTP-01 challenge responder are prepared for you.

## Mission

Configure HAProxy 3.4 to route `app.lab.test` to the local backend, redirect
HTTP to HTTPS, and obtain the certificate through HAProxy's native ACME client.
Keep the ACME account key private and prove that a renewed certificate is
served while the proxy process remains running.

Native ACME support is experimental in HAProxy 3.4 and requires
`expose-experimental-directives`. The reference solution is not included in
the guides.

## What is asked

### Criteria

- `app.lab.test` serves the expected backend over HTTPS.
- HTTP requests receive a permanent redirect to HTTPS.
- HAProxy serves a certificate for `app.lab.test` issued by the running
  Pebble authority, and a renewed certificate is served after renewal.
- The ACME account key has mode `0600`.
- TLS 1.2 succeeds; TLS 1.0 and TLS 1.1 are rejected.
- The certificate renewal does not restart HAProxy and the service remains
  available.

HAProxy native ACME support is experimental. The reference solution is not
included in the guides.
