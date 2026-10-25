# Scenario

You are taking over an unfamiliar Traefik deployment. Users report that the
`app.lab.test` service is unavailable. The dashboard has not been reviewed,
and there is no useful monitoring for the proxy.

## Mission

Within 75 minutes, secure the administration route, add response security
headers and rate limiting, configure filtered JSON access logs and Prometheus
metrics with an alert for 5xx responses, and restore the application.

The initial incident is intentionally undocumented. Use the observed HTTP
response and Traefik logs to identify the failing component. Record the
symptom, log evidence, cause, correction, and successful post-change response
in `/opt/pub-epreuve-niveau-deux/incident-report.txt`.

No hints are provided. The reference solution is not included in the guides.
