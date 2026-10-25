# Scenario

`epreuve.test` answers on `edge.lab`, in TLS, behind a router that forwards
to a protected backend carrying a business value and its backup. All of it
was put in place before you arrived: you are handed a running service, not
a blank machine. Shortly after it went live, an incident was introduced,
without telling you which layer it touches.

## Mission

First, understand and document what you are looking at: produce an
architecture dossier for the service as it actually is. Then prove it
works, from `poste.lab`, the independent client, with data you did not
pick in advance and without ever relaxing TLS validation. Somewhere along
the way you will notice the service is not behaving as the dossier says it
should: diagnose the actual cause from what you observe, repair it with a
minimal change, and explain your reasoning. Finally, exercise the backup
already sitting on `edge.lab`: restore from it and show the result can be
trusted, not just that it runs.
