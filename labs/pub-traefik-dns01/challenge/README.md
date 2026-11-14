# Challenge: a DNS-01 wildcard, with a limited identity

In `/opt/pub-traefik-dns01`, set up Traefik in front of a service that answers
any name of `boutique.lab.test`, with a wildcard certificate obtained through
the ACME DNS-01 challenge from the test authority.

## Criteria

- a name of `boutique.lab.test` drawn at random answers over HTTPS under
  strict verification, with the wildcard `*.boutique.lab.test` issued by this
  session's authority;
- the challenge was published through the bench's DNS provider;
- the account that published it is not `admin`, holds only the zone
  `boutique.lab.test`, and is refused a publication outside that zone;
- the test authority is the one the bench set up: solving the lab does not go
  through weakening it;
- each challenge record that was published was removed afterwards.

The tests observe the served certificate, the provider's journal and the
platform's fingerprint. They validate neither a particular configuration nor
the Compose files.
