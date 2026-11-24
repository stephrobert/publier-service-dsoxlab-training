# Configure HTTPS and ACME in Traefik

## The situation

You administer `edge.lab`. The `app.lab.test` service must be available over
HTTPS behind Traefik. A test ACME authority is already running on the machine
and issues short-lived certificates so renewal can be observed during a lab.

## Mission

Configure Traefik to obtain and renew the ACME certificate for `app.lab.test`
automatically, without manual intervention after startup. HTTP requests must
redirect to HTTPS, the ACME storage must be protected, and obsolete TLS
protocol versions must be rejected.

The proof is not limited to a certificate in storage: the storage file must
have restrictive permissions, the authority's log must show at least two
distinct issuances, and an HTTPS client must receive the renewed certificate,
valid for the expected name and issued by this session's authority.

`/opt/pub-traefik-acme/LISEZ-MOI.txt` describes the available services and
constraints on the machine.

## Secure HTTPS and prove automatic renewal

In `/opt/pub-traefik-acme`, configure Traefik in front of the `app.lab.test`
service. Protect ACME storage, redirect HTTP to HTTPS, and reject TLS 1.0 and
1.1.

### Criteria

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
