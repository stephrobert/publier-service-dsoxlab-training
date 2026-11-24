# The task

## The situation

A business route runs on `edge.lab`, behind a log pipeline and a metrics
exporter that are both perfectly healthy: the previous team made sure
collection itself never fails. Nobody, however, ever wrote down what the
service level indicator actually means, tuned the alert against a real
failure, or taught the monitoring to tell a genuine outage apart from a
quiet night. The on-call engineer who opened the current dashboard could not
tell whether last night's silence meant everything was fine or that nobody
was looking.

## Mission

Read `/home/student/README-obs`, then, on `edge.lab`:

- Write `/home/student/sli.yaml`: the route, the exclusions and the success
  codes that define the SLI.
- Edit `/etc/pub-obs/politique.yaml` (re-read continuously, no restart
  needed) so the alert fires on a real outage you will inject and clears
  once you remove it, and so the evaluator tells apart a real failure, an
  absence of traffic, and a stalled collection pipeline instead of
  confusing them.
- Write `/home/student/correlation.yaml`: the backend and duration you find
  in the access log for the incident already logged and named in the
  README.

## What is asked

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
