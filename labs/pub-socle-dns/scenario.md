# Scenario

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
