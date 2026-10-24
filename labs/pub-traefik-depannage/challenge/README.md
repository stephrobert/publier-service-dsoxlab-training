# Challenge: diagnose and repair Traefik

Five faults have been injected across independent Traefik routes. Inspect the
proxy and access logs before changing the file-provider configuration.

## Criteria

- `notfound.lab.test` returns HTTP 200 instead of 404.
- `badgateway.lab.test` returns HTTP 200 instead of 502.
- `timeout.lab.test/slow` returns HTTP 200 instead of 504.
- The certificate served for `tls.lab.test` includes that hostname in its
  subject alternative names.
- `loop.lab.test` reaches the backend through HTTP-to-HTTPS redirection
  without entering a redirect loop.
- Traefik applies the dynamic changes without being restarted.

The tests verify live HTTP responses, the TLS certificate presented by the
proxy, and the redirect sequence. The reference solution is not included in
the guides.
