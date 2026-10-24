# Challenge: protected Traefik administration

Replace the vulnerable setup on `edge.lab` with HTTPS administration access on
`admin.lab.test`.

## Criteria

- host port 8080 no longer listens;
- without credentials, the dashboard and API return HTTP 401 over HTTPS;
- with the provided credentials, both return HTTP 200;
- the client validates the test certificate for `admin.lab.test`;
- Traefik uses the pinned Docker socket proxy without mounting the socket
  directly;
- responses have security headers and an authenticated burst triggers HTTP 429.

Tests observe real port and route behavior, socket mounts, HTTP headers, and
the response under load; they do not check a particular Compose file.
