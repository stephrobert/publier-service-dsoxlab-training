# The task

Write `/home/student/fiche-service.yaml` with these keys:

```yaml
service: <systemd unit that serves the application>
utilisateur: <user the process runs as>
ecoute: <TCP port the application listens on>
dependances:
  - nom: <systemd unit of the dependency>
    utilisateur: <user it runs as>
    port: <TCP port it listens on>
redemarrage:
  conserve: [<state values kept after restarting the application>]
  perdu: [<state values lost after restarting the application>]
recette:
  - <at least three observable acceptance criteria>
```

The tests compare each value with the running system, bring the business
function back to be checked (`/api/livres` must answer HTTP 200 with the real
list) and measure what a restart of the application keeps. The state values are
the names returned by the application's state endpoint.
