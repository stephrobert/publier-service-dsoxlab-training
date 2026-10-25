# The task

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
