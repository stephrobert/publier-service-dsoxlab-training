# pub-traefik-mtls

**Audience:** the learner.

Protect a Traefik route with mutual TLS: the entry point must demand and
verify a client certificate, and Traefik itself must verify the backend's
certificate rather than trust it blindly. Add resistance to forged
forwarding headers and prove that rotating certificates does not silently
disable access control.

## What you will be able to do

- Configure a Traefik TLS option that requires and verifies client
  certificates against a CA.
- Configure a server transport that verifies a backend's certificate
  against its own CA, without disabling verification.
- Recognize why forwarded identity headers from an untrusted hop must be
  ignored.
- Rotate certificates without reopening a hole in access control.

A client CA, a backend CA, valid certificates and several invalid variants
are prepared. The task and available paths are described in
`/opt/pub-mtls/README`.
