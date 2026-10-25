# Scenario

A web service is published on `edge.lab` and answers correctly. Before it goes
live, a security review notes that it was started in a hurry: the application
and its administration interface listen as widely as the entry point does.
Anyone on the network could skip the entry point and talk to them directly.

## Mission

Read `/home/student/README-exposition`, discover what really listens on
`edge.lab`, and write the flow matrix in `/home/student/flux.yaml`. Then close
every path that bypasses the entry point, so that the public service stays
reachable from `poste.lab` while the backend and the administration are only
reachable from `edge.lab` itself.
