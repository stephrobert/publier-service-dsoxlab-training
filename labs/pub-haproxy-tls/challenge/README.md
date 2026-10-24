# Challenge: issue and renew a HAProxy certificate

## Criteria

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
