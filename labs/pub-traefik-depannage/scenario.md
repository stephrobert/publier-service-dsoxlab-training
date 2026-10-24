# Scenario

Several services behind Traefik have become unreliable. Users report missing
pages, gateway failures, slow requests, a certificate warning, and redirects
that never finish.

## Mission

Use the proxy and access logs to locate each fault, repair the dynamic
configuration, and verify the real responses. Traefik must stay running while
the file provider applies the changes.
