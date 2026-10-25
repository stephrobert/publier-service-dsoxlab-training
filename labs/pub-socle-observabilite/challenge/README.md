# The task

1. Write `/home/student/sli.yaml`:

```yaml
route: /commande
exclut: [/sante]
code_min_succes: 200
code_max_succes: 299
```

The tests apply exactly these fields to the real access log, both to a
known historical batch and to a fresh batch they generate themselves, and
compare the result to the correct definition.

2. On `edge.lab`, edit `/etc/pub-obs/politique.yaml` (re-read continuously,
   no restart needed):

```yaml
collecte:
  staleness_max_s: <n>
trafic:
  seuil_minimum: <n>
alerte:
  seuil_taux_erreur: <0..1>
```

The tests read `http://127.0.0.1:<port>/diagnostic` on the evaluator (port
in `/home/student/README-obs`) while injecting, one at a time:

- a real outage (the `panne` flag described in the README): the evaluator
  must classify it as `panne_reelle` with `firing: true`, then clear once you
  remove the flag;
- a stopped traffic generator: it must classify `absence_trafic`, never
  `panne_reelle`;
- a frozen metrics exporter: it must classify `collecte_perdue` once your
  staleness threshold is crossed, neither too fast nor never.

3. Write `/home/student/correlation.yaml` for the incident named in the
   README:

```yaml
requete_id: <the incident id>
backend: pub-obs-metier
code: <the code you find in the log>
duree_ms: <the latency you find in the log>
```

The tests read the same log line themselves and compare it to your file.
