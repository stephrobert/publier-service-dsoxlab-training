# The mission

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
