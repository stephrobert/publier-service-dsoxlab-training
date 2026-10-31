# The task

Work from `edge.lab` for anything operator-facing and from `poste.lab` for
anything client-facing. The bench is described in
`/opt/pub-epreuve-nginx/LISEZ-MOI.txt`. From `poste.lab`, fetch the test
authority root from `https://<edge-ip>:15000/roots/0` (the `-k` is only for
reaching Pebble's management interface, never for the service) and use
`curl --cacert <root> --resolve <name>:443:<edge-ip>`.

The scenario lists the deliverables, the entry points the validation calls
and the fixed locations. In short:

1. **Publish** `www.epreuve.test` (the site, from
   `/opt/pub-epreuve-nginx/site`) and `api.epreuve.test` (the API on
   `127.0.0.1:18201`), HTTPS strict, HTTP redirecting, unknown names refused.
   Provide `renouveler-certificats`.
2. **Set the policy**: `/admin` behind the supplied credentials, hidden files
   refused, only `GET` and `HEAD` on the API, backend unreachable from the
   network, public API answer cached, private answers never shared.
3. **Operate**: `/v1/flux` streamed, JSON log in
   `/var/log/nginx/epreuve.json`, status page on `127.0.0.1:8081`, and
   `sonde-alerte`.
4. **Incident**: write `/home/student/recette-initiale.md` when your recette
   passes. An incident follows. Write `/home/student/incident.yaml`:

   ```yaml
   couche: tls    # one of: amont, tls, droits, entetes
   composant: "..."
   explication: "..."
   ```

   Name only the real cause in `composant`; hypotheses you ruled out belong in
   `explication`. Repair it with the smallest change, without weakening
   anything, and prove the service answers again, several times.
5. **Recovery**: provide `sauvegarder-service` and `restaurer-service`. The
   validation destroys the configuration and the certificate files, runs your
   restore, reboots the machine and replays the whole recette.
