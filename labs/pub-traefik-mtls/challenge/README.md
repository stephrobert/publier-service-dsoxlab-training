# The task

Fix `/opt/pub-mtls/dynamic/routes.yaml`: set `clientAuthType` to
`RequireAndVerifyClientCert` on the `mtls` TLS option so a client
certificate signed by the client CA is actually required and verified; set
`insecureSkipVerify` to `false` and add `rootCAs: [backend-ca.crt]` on the
`verif-backend` server transport so Traefik verifies the backend's own
certificate instead of trusting it blindly. Then fix
`/opt/pub-mtls/traefik-static.yaml`: scope `entryPoints.websecure.forwardedHeaders.trustedIPs`
to the authorized upstream proxy's address (`172.30.10.10/32`) only, and
restart Traefik (`docker restart pub-mtls-traefik`) since this is a static
setting. The checks call the real HTTPS entry point on port 8443 (direct
clients) and the authorized proxy on port 8080 (indirect clients), and
rotate the client CA live to confirm access control survives it.
