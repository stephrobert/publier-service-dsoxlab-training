# The task

## The situation

Traefik on `edge.lab` exposes a sensitive application over HTTPS. The
entry point's TLS option currently accepts any connection, client
certificate or not: whoever can reach the port gets in. On the other
side, Traefik talks to the backend over HTTPS too, but currently trusts it
without checking its certificate at all, so a backend presenting the wrong
certificate would go unnoticed. A reverse proxy sitting in front of this
one is allowed to forward identity headers, but nothing stops a direct,
untrusted caller from forging the same headers.

## Mission

Require a valid client certificate signed by the lab's client CA before
Traefik accepts a connection; reject missing, foreign or expired
certificates. Make Traefik verify the backend's certificate against the
lab's backend CA instead of skipping verification, so a wrong certificate
on the backend side is caught. Make sure forged forwarding headers from an
untrusted, direct caller do not change the identity Traefik records, while
headers from the lab's authorized upstream proxy still do. Finally, rotate
the certificates and prove access control still holds.

## What is asked

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
