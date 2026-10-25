# Scenario

A storefront on `edge.lab` is reached through two reverse proxies: a first
one that actually receives the connection from the outside, and a second
one behind it that forwards to the application. The application logs, for
every request, the address it was told to trust and the identity it was
told to trust. During an audit, someone noticed that both of these were
simply whatever the original client had sent, carried unchanged through
both hops. Nothing had been technically broken: TLS had succeeded, the
chain answered. But a request coming from the public internet could claim
to originate from an internal network, and could claim to be an
administrator, and the application had no way to tell the difference.

You are asked to understand exactly which hop is responsible for deciding
what to trust, and to make sure none of this can be forged from outside the
chain again.

## Mission

Read `/home/student/README-rp` on `edge.lab`, then produce, still on
`edge.lab`, `/home/student/diagnostic.yaml`: the facts you established by
observation about which hop terminates TLS, which ones relay in plain
HTTP, and how origin and identity currently flow through the chain. Then
close the path described above, and every direct path that still lets a
client reach a hop it was never meant to reach.

The test authority is already installed on `poste.lab`, at
`/home/student/ca.pem`.
