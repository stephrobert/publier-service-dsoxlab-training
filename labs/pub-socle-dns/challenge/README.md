# The task

## The situation

The shop site `shop.pub.test` runs in version v1. Version v2 is ready on other
addresses and must go live. Last time, half of the users kept landing on the old
version for an hour after the change. You are asked to do the switch properly,
and to be able to go back at once if v2 misbehaves.

## Mission

Read `/home/student/README-dns`, then produce on `edge.lab`:

- `/home/student/dns.yaml`, the facts you found about the zone;
- `/home/student/basculer.sh`, a script that switches `shop.pub.test` to a
  given version and makes the change visible to clients quickly.

The site is checked from `poste.lab`, through the caching resolver, exactly as
a user would reach it.

## What is asked

1. Write `/home/student/dns.yaml`:

```yaml
serveur_autoritaire: <address of the server that is authoritative for pub.test>
ttl_initial: <TTL in seconds of the shop records before you touched anything>
types_a_basculer: [<record types to change to move shop to v2>]
```

2. Write `/home/student/basculer.sh`, run on `edge.lab` as
   `bash basculer.sh <v1|v2>`. It must make `shop.pub.test` point to the given
   version for both IPv4 and IPv6, and make clients see it within seconds
   (not after the original TTL). It must work again when called a second time,
   in either direction.

The tests call your script themselves, in both directions, then fetch
`http://shop.pub.test/` from `poste.lab` over IPv4 and over IPv6 and check which
version answers. The site must finish on v2.
