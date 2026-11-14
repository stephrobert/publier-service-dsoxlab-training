# Issue a wildcard certificate with DNS-01

You administer `edge.lab`. The shop publishes new subdomains of
`boutique.lab.test` every week, and the team no longer wants to request one
certificate per name. It needs a **wildcard certificate** `*.boutique.lab.test`,
served by Traefik, and the authority only issues one through the ACME
**DNS-01** challenge: you must prove that you control the zone by publishing a
TXT record in it.

The bench runs without Internet. A test ACME authority, Pebble, reads the TXT
records on a test authoritative DNS server. That server is not administered
directly: you go through the API of a DNS provider, as with a real host. You
were given its administrator account, which holds every zone.

## Mission

Obtain the wildcard through Traefik, served to any name of `boutique.lab.test`,
with no manual step after startup. The automation that publishes the challenge
must not receive the keys to the whole DNS: give it an identity limited to its
own zone. The temporary records must disappear once the challenge is played.

`/opt/pub-traefik-dns01/LISEZ-MOI.txt` describes the bench, and
`/home/student/fournisseur-dns-admin.txt` the provider account.
