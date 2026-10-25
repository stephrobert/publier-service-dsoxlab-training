# Challenge: observe Traefik

Traefik serves `observabilite.lab.test`; its `/fail` backend path deliberately
returns HTTP 503. Prometheus already scrapes the local target configured in
`/opt/pub-observabilite/prometheus/prometheus.yml`.

## Criteria

- Write Traefik access logs as JSON to
  `/opt/pub-observabilite/logs/access.json`.
- Filter the access log to HTTP 5xx responses and retain the host, path, and
  downstream status fields. Do not log request headers.
- Enable Traefik Prometheus metrics on a loopback-only entry point at
  `127.0.0.1:8082`, with router and entry point labels.
- Configure Prometheus to alert when Traefik records an HTTP 5xx response, and
  reload Prometheus after changing its rules.
- Keep the Prometheus UI/API bound to loopback.

The tests generate real HTTP traffic and inspect the JSON log and Prometheus
HTTP API. They do not require a particular alert name or file layout.
