# Assessment: protect, observe, and diagnose

## The situation

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

## What is asked

### Criteria

- The application route returns HTTP 200 after the unknown outage is repaired.
- The dashboard requires authentication; unauthenticated access returns 401.
- Application responses include the required security headers, and a request
  burst triggers HTTP 429.
- JSON access logs retain only 5xx responses and omit request-header fields.
- Prometheus reports the Traefik target up and fires an alert after a real 503.
- `incident-report.txt` records the observed status, log evidence, diagnosis,
  correction, and successful response.
- The assessment is completed within 75 minutes; no hints are provided.

The reference solution is not included in the guides.
