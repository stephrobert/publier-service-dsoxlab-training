# Assessment: protect, observe, and diagnose

## Criteria

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
