# The task

Work from `poste.lab` for anything client-facing, and from `edge.lab` for
anything operator-facing. `/home/student/ca.pem` on `poste.lab` is the test
authority: never use `curl -k` / `--insecure`.

1. Run the acceptance matrix from `poste.lab` against `https://service.mes.test/`:
   DNS (`dig`, the real resolver, no `--resolve`-only shortcut for this
   check), TLS and the business route `/catalogue` (`--cacert ca.pem`), and
   the internal route `/interne/compte`, which must be refused (403).

   One of these currently fails: `/etc/pub-mes/route.yaml` on `edge.lab`
   carries a field that still exposes the internal route. Fix it; the
   router re-reads this file on every request.

   Then write `/home/student/recette.yaml`:

   ```yaml
   dns_ok: true
   tls_ok: true
   http_ok: true
   refus_ok: true
   ```

2. Write `/home/student/restaurer.sh`, a script run on `edge.lab` that
   restores `/etc/pub-mes/route.yaml` and `/var/lib/pub-mes/stock.json` from
   `/var/backups/pub-mes/` and makes the router serve the real business
   value again. The tests actually delete both active files before running
   your script: a backup nobody has restored from is a belief, not proof.

3. Write `/home/student/revenir-origine.sh`, a script run on `edge.lab` that
   brings `origine_active` in `/etc/pub-mes/route.yaml` back to `a` and
   makes the router pick it up immediately. Editing the file alone is not
   enough: `origine_active` is cached for `ttl_cache_s` seconds. Read the
   router's behaviour (`/opt/pub-mes/router.py` is on `edge.lab`) to find
   what forces an immediate reload.

4. Write `/home/student/limites.yaml`, a short honest report naming what a
   real, Internet-facing release would still need beyond this lab: a public
   resolver, an external client, a public certificate authority.
