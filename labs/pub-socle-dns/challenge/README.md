# The task

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
