# Scenario

Two applications are published behind the same address and port on
`edge.lab`: `boutique.dht.test`, a public storefront, and
`compte.dht.test`, where customers manage their account. Each has its own
name, its own certificate, and its own backend. A visitor who was sent the
wrong link once ended up looking at the account application while the
browser still showed a padlock and the storefront's own certificate details
nobody had checked closely. Nothing was broken: TLS had succeeded, the
certificate chain was genuine. The application behind it was simply not the
one the visitor, or the padlock, suggested.

You are asked to understand exactly why that happened, and to make sure a
third name, one that was never registered anywhere, can no longer reach
either application by accident.

## Mission

Read `/home/student/README-dht` on `edge.lab`, then produce, still on
`edge.lab`, `/home/student/diagnostic.yaml`: the facts you established by
observation, from `poste.lab` and from `edge.lab`, about DNS resolution, TLS
certificate selection, and HTTP application routing. Then close the path
described above.

The test authority is already installed on `poste.lab`, at
`/home/student/ca.pem`.
