# The task

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
