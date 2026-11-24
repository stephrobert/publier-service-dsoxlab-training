# Protect Traefik administration

## The situation

On `edge.lab`, a Traefik instance currently exposes its administration API
directly on port 8080. Anyone who can reach that port can inspect the proxy
configuration without authenticating.

## Mission

Remove this direct access and provide an authenticated HTTPS administration
endpoint on `admin.lab.test`. Traefik must reach the Docker API through a
restricted socket proxy, not by mounting the socket directly. Add security
headers and a rate limit that returns 429 under load. An authorized operator
must be able to access the dashboard and API; without credentials, both must
deny access.

The test certificate, validation credentials, socket-proxy image, and working
directory are described in `/opt/pub-admin/LISEZ-MOI.txt`.

## Protected Traefik administration

Replace the vulnerable setup on `edge.lab` with HTTPS administration access on
`admin.lab.test`.

### Criteria

- host port 8080 no longer listens;
- without credentials, the dashboard and API return HTTP 401 over HTTPS;
- with the provided credentials, both return HTTP 200;
- the client validates the test certificate for `admin.lab.test`;
- Traefik uses the pinned Docker socket proxy without mounting the socket
  directly;
- responses have security headers and an authenticated burst triggers HTTP 429.

Tests observe real port and route behavior, socket mounts, HTTP headers, and
the response under load; they do not check a particular Compose file.
