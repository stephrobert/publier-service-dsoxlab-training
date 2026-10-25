# Challenge: Traefik middleware behavior

Traefik on `edge.lab` already routes `middleware.lab.test` to a local web
backend. Improve the responses without interrupting the proxy.

## Criteria

- requests under `/portal/` reach the backend with the prefix removed;
- requests under `/legacy/` receive a permanent redirect to the matching
  `/docs/` path;
- portal responses include `X-Content-Type-Options: nosniff` and
  `X-Frame-Options: DENY`;
- clients that accept gzip receive compressed portal responses;
- Traefik remains running without being restarted.

Tests inspect HTTP status codes, response headers, and the backend-observed
request path, and confirm the original Traefik process remains in place. They
do not require a particular file layout.
