# The task

## The situation

`depan.test` answers on `edge.lab`, in TLS, behind a router that forwards to
a protected backend. Someone reports it is misbehaving. Nobody has told you
which layer: it could be the name, the network path, the certificate, the
route configuration, or the backend process itself. The journal also
carries an unrelated warning that looks alarming but leads nowhere.

## Mission

Observe from `poste.lab`, the independent client, and from `edge.lab`, the
operator side. Form a hypothesis, test it, and name the actual faulty layer
and component, not a plausible guess. Repair it with the smallest change
that fixes it, then prove the service works again and that no protection,
the forbidden route, the backend's isolation, or TLS itself, was weakened
along the way.

## What is asked

Work from `poste.lab` for anything client-facing, and from `edge.lab` for
anything operator-facing. `/home/student/ca.pem` on `poste.lab` is the test
authority: never use `curl -k` / `--insecure`.

1. Observe from `poste.lab`: `dig depan.test A`, then
   `curl --cacert ca.pem --resolve depan.test:443:<edge-ip>
   https://depan.test/`. One of five layers is broken: DNS, transport
   (nothing answers on 443), TLS (the certificate is not trusted), the route
   (the router answers but the backend call fails), or the backend
   (connection refused upstream). A background warning may show up in
   `journalctl` on `edge.lab`; it is unrelated noise, not a clue.

   Keep `/home/student/journal.md` on `edge.lab` while you investigate:
   timestamped observations, the hypothesis you form, the targeted test you
   ran, and whether it confirmed or refuted it.

2. Once you know the actual layer and component, write
   `/home/student/diagnostic.yaml` on `edge.lab`:

   ```yaml
   couche: route    # one of: dns, transport, tls, route, backend
   composant: "..."
   explication: "..."
   ```

   Name only the real cause. Listing every possible layer "just in case"
   does not count as a diagnosis.

3. Repair it on `edge.lab` with the smallest change that fixes it. The
   relevant files live under `/etc/pub-dep/` (`route.yaml`), the systemd
   units `pub-dep-router.service` and `pub-dep-backend.service`, and the
   unbound zone in `/etc/unbound/unbound.conf.d/pub-dep.conf`.

4. Prove from `poste.lab`, after the fix: the service answers `200` on `/`
   (retested three times), `/admin` still answers `403`, the backend port is
   still unreachable directly, and port 443 still speaks TLS only. None of
   these three protections existed to be broken by your fix; they exist to
   be checked that your fix did not break them either.
