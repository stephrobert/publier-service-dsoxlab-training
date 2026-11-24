# The task

## The situation

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

## What is asked

Work from `poste.lab` for anything client-facing, and from `edge.lab` for
anything operator-facing. `/home/student/ca.pem` on `poste.lab` is the test
authority: never use `curl -k` / `--insecure`.

1. **Dossier (`besoin`).** Observe the service as it actually runs:
   `dig epreuve.test A`, `curl --cacert ca.pem --resolve
   epreuve.test:443:<edge-ip> https://epreuve.test/`, `systemctl status
   pub-eps-router pub-eps-backend` on `edge.lab`. Write
   `/home/student/dossier.md` on `edge.lab`: the names involved, the flow
   from client to backend (what terminates TLS, what is reachable only
   from where), the identities (who signed the certificate, who it is
   issued to), and the responsibilities (what the router does, what the
   backend enforces on its own, such as `/admin`). This dossier is judged
   on the coherence of what you observed, not on its length.

2. **Proof (`preuve`, critical).** From `poste.lab`, prove the service
   really works for an independent client: request `/` with a nonce you
   choose at the time (`?nonce=...`) and check it comes back in the
   response, along with the actual business value, retrieved under strict
   TLS validation (never `-k`). Also confirm `/admin` is refused (`403`).

3. **Incident (`incident`, critical).** At some point you will notice the
   service does not answer as the dossier says it should: an incident,
   not announced, has been introduced on one of five layers (DNS,
   transport, TLS, the route, or the backend). Observe, form a
   hypothesis, and once you know the real layer and component, write
   `/home/student/incident.yaml` on `edge.lab`:

   ```yaml
   couche: route    # one of: dns, transport, tls, route, backend
   composant: "..."
   explication: "..."
   ```

   Name only the real cause, backed by what you actually observed.
   Listing every possible layer "just in case" does not count as a
   diagnosis. Repair it with the smallest change that fixes it, under
   `/etc/pub-eps/` (`route.yaml`), the systemd units
   `pub-eps-router.service` and `pub-eps-backend.service`, or the unbound
   zone in `/etc/unbound/unbound.conf.d/pub-eps.conf`. Prove the service
   answers again, retested several times.

4. **Recovery (`reprise`, critical).** A backup already sits in
   `/var/backups/pub-eps/` (`route.yaml.bak`, `donnees.json.bak`): it was
   taken before the incident, but nobody has proved it actually restores
   anything. Write `/home/student/restaurer.sh` on `edge.lab`: a script
   that restores `/etc/pub-eps/route.yaml` and
   `/var/lib/pub-eps/donnees.json` from that backup directory, so the
   router serves the real configuration and the backend serves the real
   business value again, with no change to the certificate or the
   authority that signed it. It will be run with `sudo bash
   /home/student/restaurer.sh` after both live files have been removed:
   make sure it does not depend on anything else still being in place.
