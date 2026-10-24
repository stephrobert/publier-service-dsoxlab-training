# Protect Traefik administration

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
