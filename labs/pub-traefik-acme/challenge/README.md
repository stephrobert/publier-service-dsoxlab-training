# Challenge: secure HTTPS and prove automatic renewal

In `/opt/pub-traefik-acme`, configure Traefik in front of the `app.lab.test`
service. Protect ACME storage, redirect HTTP to HTTPS, and reject TLS 1.0 and
1.1.

## Criteria

- the ACME storage file has mode `0600`;
- HTTP redirects to HTTPS with status 301;
- TLS 1.0 and 1.1 are rejected;
- the client reaches the service over HTTPS and validates the certificate with
  the provided Pebble CA;
- Pebble logs at least two distinct certificates for the service within the
  test's time limit;
- Traefik serves the latest issued certificate to the client, valid for
  `app.lab.test`.

Tests observe client responses and the authority's logs. They do not validate
a particular configuration or Compose files.
