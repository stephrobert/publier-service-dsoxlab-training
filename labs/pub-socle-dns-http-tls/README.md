# pub-socle-dns-http-tls

**Audience:** the learner.

Learn why a valid, trusted certificate does not prove you reached the right
application: TLS picks a certificate from the SNI sent during the handshake,
HTTP then picks the application from the Host header sent afterwards, and
these are two separate decisions. Learn also to tell a normal DNS lookup from
one that deliberately bypasses DNS, and why a name nobody registered should
never reach an application by accident.

## What you will be able to do

- Compare a normal DNS resolution with a forced one that bypasses the
  resolver entirely.
- Vary the TLS SNI while keeping the same address, and check the returned
  certificate's chain and SAN without disabling verification.
- Vary the HTTP Host header while keeping the same SNI, and explain which
  application actually answers.
- Close the path that lets a name nobody registered reach an application by
  accident.

Your observations happen from `poste.lab` and `edge.lab`; the deliverable is
written on `edge.lab`. `challenge/README.md` describes it precisely.
