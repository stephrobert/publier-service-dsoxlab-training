# The mission

## The situation

You take over the entry point of a small platform on `edge.lab`. HAProxy is
installed and has **no mission**: no listener, no certificate, no route. Two
services already run behind it, started in a hurry: a **catalogue** and a
**notifications** service. Nobody has published them properly, and nobody has
tried to lose and recover the entry point. A test certificate authority and an
ACME client are provided.

On the same machine, a second HAProxy instance named **archives** has served
an application for a while. It worked. Then something broke, and nobody says
what.

You get a business need and a recipe, never a configuration to copy:
`/opt/pub-epreuve-haproxy/recette.txt` states what must happen, and not one
directive.

## Mission

**Part 1, deliver two services.** Publish the catalogue and the notifications
service behind HAProxy, each under its own name, in HTTPS, with a certificate
per name that you obtain and renew through a script you write. Control access
to the administration routes. Make sure a client cannot choose the address the
services see for it, and that a client who sends too much is slowed down and
released. Let a long event stream through. Make the proxy observable. Close
everything that bypasses the entry point. Then prove you can lose HAProxy,
its configuration and the business data, and get all of it back from backups.

**Part 2, diagnose an unknown fault.** The archives instance has a fault
drawn at random among five families. Find which one, repair it **without
removing any safeguard**, and write down what you found.

## What the machine grades, and what a reviewer reads

Twenty checks, five points each, played from `poste.lab`, the independent
client, under strict TLS validation (never `curl -k`).

| Domain | Checks | Points |
|---|---|---|
| Publication and protocols | certificate cycle, HTTPS per name, unknown name and redirect, verified load | 20 |
| Security and trust | isolation of backends, administration, source address, rate limit, private keys | 25 |
| Observability and flow | long stream, metrics, a stopped service read in the metrics, refusals counted | 20 |
| Diagnosis | family and component, service repaired, trust and probes kept, limit and bound kept | 20 |
| Recovery and rollback | full restore, reload without outage, reboot | 15 |

A machine cannot judge reasoning. The `famille` and `composant` fields of
`incident.yaml` are compared to the fault that was laid; the `explication`
field is **read by a reviewer**, and only its presence is checked here. The
reviewer also reads your configuration and your scripts, and asks you to
justify your choices.

## Rules of the exam

- The test authority issues certificates valid for **five minutes**. The
  validation runs your renewal script as often as it needs a fresh certificate.
- The test authority draws a new root and forgets its accounts at every start.
  The validation reads the root again before each check.
- A fix that removes a safeguard to restore the service (turning verification
  off, removing probes, lifting a limit) does not count: the checks that
  follow the repair look for those safeguards.
- The last check restarts the machine, then replays the recipe. Everything
  must come back by itself.

## What is asked

Work from `poste.lab` for everything a client sees, and from `edge.lab` for
everything an operator does. `/home/student/racine-acme.pem` on `poste.lab` is
the test authority's root: never use `curl -k` / `--insecure`. Read
`/home/student/README-epreuve` and `/opt/pub-epreuve-haproxy/recette.txt` on
`edge.lab` in full: they say what must happen.

The assessment has two independent parts. Time budget: 150 minutes.

1. **Deliver two services (domains: publication, security, observability,
   recovery).** HAProxy is installed and has no mission. The `catalogue` and
   `notifications` services run on ports 18301 and 18302, started in a hurry.
   Deliver, with the configuration of HAProxy and two scripts:

   - the two names in HTTPS, one certificate per name, obtained from the test
     authority through the provided ACME client;
   - `/opt/pub-epreuve-haproxy/renouveler`, executable, which renews both
     certificates and puts them into service without restarting HAProxy. The
     validation **runs** it, several times, and again after a reboot;
   - the access, source-address, rate-limit, isolation, stream and metrics
     requirements of the recipe;
   - the backup of your configuration in
     `/var/backups/pub-epreuve-haproxy/haproxy.cfg.bak`, and
     `/opt/pub-epreuve-haproxy/restaurer`, executable, which restores the
     catalogue's business data **and** the HAProxy configuration from the
     backups and brings HAProxy back. The validation breaks all three, then
     runs it.

2. **Diagnose an unknown fault (domain: diagnosis).** The `archives` instance
   (port 8088, its own configuration, unit and socket, listed in the recipe)
   carries a fault drawn among five families. Repair it without removing any
   safeguard, then write `/home/student/incident.yaml` on `edge.lab`:

   ```yaml
   famille: routage    # one of: routage, sonde, confiance, limite, delai
   composant: "..."
   explication: "..."
   ```

   Name the real cause, backed by what you observed. Listing every family "just
   in case" is not a diagnosis. Hypotheses you ruled out belong in
   `explication`.
