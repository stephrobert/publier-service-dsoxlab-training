# The task

## The situation

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

## What is asked

On `edge.lab`, write `/home/student/diagnostic.yaml`:

```yaml
resolveur: <IP address of the resolver poste.lab actually queries for dht.test>
nom_inconnu_resout: <true|false: does normal DNS resolution answer for the unknown name?>
sni_boutique: boutique.dht.test
sni_compte: compte.dht.test
host_decide_routage: <true|false: does the HTTP Host header, not the TLS SNI, decide which application answers?>
application_si_sni_boutique_host_compte: <"boutique"|"compte": with SNI=boutique.dht.test and Host: compte.dht.test, which application answers?>
nom_inconnu_doit_etre_refuse: true
```

Then, still on `edge.lab`, edit `/etc/pub-dht/routes.yaml` so that a name
nobody registered (neither in DNS nor in this file) is refused outright,
instead of silently reaching whichever application happens to be declared
first.

The tests query the router themselves, from `poste.lab` with `--cacert
/home/student/ca.pem` and never `-k`, varying SNI and Host independently, and
separately probe the unknown name. They check your file against what they
observe, and check that the unknown name is genuinely refused, not just
described as such.
