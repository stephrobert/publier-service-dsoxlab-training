# Scenario

Four TLS endpoints were deployed on `edge.lab` to answer under the name
`svc.tls.test`. Before anything is published, a security review asks for proof
that each endpoint really is what it claims to be, using the test root of
trust that was handed over for this review, not the operating system's public
trust store.

## Mission

Read `/home/student/README-tls`, connect to each of the four endpoints with
the given root certificate, and write `/home/student/verdict.yaml` stating
whether each endpoint is accepted and, when it is refused, why: a name that
does not match, a chain that does not lead back to the given root, or dates
that place the certificate outside its validity window. Do not change the
test machine's clock to do this.
