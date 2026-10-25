# Scenario

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

