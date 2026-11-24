# The task

## The situation

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

## What is asked

1. Find out which ports listen on `edge.lab` and who can reach them, from
   `edge.lab` itself and from `poste.lab`.
2. Write `/home/student/flux.yaml` with one entry per service (`public`,
   `backend`, `admin`), giving its port and whether it is reachable (`ouvert`)
   or not (`ferme`) from the client and from the host itself:

```yaml
flux:
  public:  {port: <n>, client: <ouvert|ferme>, local: <ouvert|ferme>}
  backend: {port: <n>, client: <ouvert|ferme>, local: <ouvert|ferme>}
  admin:   {port: <n>, client: <ouvert|ferme>, local: <ouvert|ferme>}
```

3. Change the system so that the matrix describes the policy of the README:
   the public service is reachable from the client, the backend and the
   administration are not, while all three stay reachable from `edge.lab`.
   If you use `nft`, put your rules in the table `inet pub_expo`.

The tests probe the three ports themselves, from `poste.lab` and from
`edge.lab`, and compare your matrix with what they observe.
