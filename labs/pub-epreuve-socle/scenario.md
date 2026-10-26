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

## What the machine grades, and what a reviewer reads

This distinction is not a formality: a machine cannot judge a document, and
pretending otherwise would mean passing incoherent text on the grounds that
it is long enough and uses the expected words.

**Graded by the validation**, because it can be compared against the real
state of the machine:

- the dossier **exists** and **names the service** it documents;
- the service answers from `poste.lab` with data chosen at run time, under
  strict TLS validation, and `/admin` stays refused;
- the **`couche`** field of `incident.yaml` names the layer that is really
  broken, and the **`composant`** field names the faulty component without
  citing an unrelated layer;
- the **`explication`** field is **present**;
- the restore runs and its result can be checked.

**Read by a reviewer, and not graded here**: whether the dossier is any
good, whether it covers names, flows, identities and responsibilities, and
the quality of the reasoning written in `explication`. Hypotheses you ruled
out belong in that field: writing them there does not count against you, it
is what a diagnosis is expected to show.
