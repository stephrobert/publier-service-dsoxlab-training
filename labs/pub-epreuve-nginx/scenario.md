# Scenario

You are handed an empty Nginx and a brief. The product team has a static
site and an API to put online under two names, `www.epreuve.test` and
`api.epreuve.test`. A local ACME authority (Pebble) and an ACME client
(lego, as a pinned container image) are available, the site content and the
API are already on `edge.lab`, and nothing else exists: no Nginx
configuration, no certificate, no backup, no alert.

The bench is described in `/opt/pub-epreuve-nginx/LISEZ-MOI.txt` and in
`/home/student/README-epreuve` on `edge.lab`. You work from `edge.lab` for
the operator side and from `poste.lab`, the independent client, to prove
what a visitor really gets. Never use `curl -k`: strict validation is part
of what is graded.

## Mission

Publish the service and operate it, in five moves.

1. **Publish.** Serve the static site on `www.epreuve.test` and the API on
   `api.epreuve.test`, over HTTPS with a strict chain, from the content where
   it already is (do not copy it). HTTP redirects to HTTPS, an unknown name
   serves nothing, and the certificates renew for real.
2. **Set the policy.** `/admin` on the API asks for the credentials of
   `/opt/pub-epreuve-nginx/admin.htpasswd` (user and password are in
   `/home/student/README-epreuve`); hidden files of the site are never
   served; the API refuses every method other than `GET` and `HEAD`; the backend is never
   reachable from the network; the public API answer is cached, and no private
   answer ever goes from one session to another.
3. **Operate.** The long stream `/v1/flux` is delivered at the backend's rhythm;
   the access log is JSON with durations that measure; a status page answers
   on the loopback interface only; an alert fires when the service is down and
   falls back when it is back.
4. **Report your initial recette, then face the incident.** When your service
   passes your own recette, write `/home/student/recette-initiale.md`. Writing
   it is what releases the incident: a few seconds later something changes on
   the machine, without telling you which layer it touches. Diagnose it from
   what you observe, repair it with the smallest change, and explain.
5. **Prove your recovery plan.** Make a backup, lose the configuration and
   the certificates, restore from your backup, then reboot the machine and
   replay the full recette without touching anything.

## Entry points the validation calls

The validation cannot know which mechanism you choose, so it calls fixed
entry points and measures the result. All of them run as root on `edge.lab`.

| Entry point | What the validation expects |
|---|---|
| `/usr/local/bin/renouveler-certificats` | renews the certificates of both names and puts the new series in service with a reload, keeping the same ACME account |
| `/usr/local/bin/sauvegarder-service` | saves what is needed to bring the service back |
| `/usr/local/bin/restaurer-service` | restores it, whether Nginx is running or stopped |
| `/usr/local/bin/sonde-alerte` | exits `0` when the service is healthy, non-zero when it is not, and returns to `0` within 90 seconds of the recovery |

Fixed locations, because a check must find them without guessing:

- the JSON access log is `/var/log/nginx/epreuve.json`, and every line carries
  at least `status`, `request_time` and `upstream_response_time`;
- the status page is `http://127.0.0.1:8081/nginx_status`;
- the ACME client keeps its data under `/opt/pub-epreuve-nginx/lego`, its
  account in `accounts/`, its HTTP-01 challenge directory is
  `/opt/pub-epreuve-nginx/defi`;
- the diagnosis is `/home/student/incident.yaml`, with the three fields
  `couche`, `composant` and `explication`.

## What the machine grades, and what a reviewer reads

**Graded by the validation**, because it can be compared with the real state of
the machine:

- **publication** (critical): the right content by name, a strict chain on both
  names, HTTP redirecting to HTTPS, and a renewal that serves a **new serial**
  without restarting Nginx or changing the ACME account, with private keys that
  are not world-readable;
- **policy** (critical): the refusal matrix (administration without or with
  wrong credentials, forged identity headers, hidden files, unused methods,
  direct access to the backend), and a cache that spares the origin for public
  answers while two alternating sessions never see each other's data;
- **operation**: the stream's rhythm, a log whose durations match facts the
  validation provokes, the loopback-only status page, and the alert in both
  directions during a controlled backend outage;
- **incident** (critical): the `couche` field names the layer that is really
  broken (`amont`, `tls`, `droits` or `entetes`), the `composant` field names
  the faulty component **without citing another variant**, the `explication`
  field is present, the service answers again several times in a row, and the
  repair lost no guarantee: strict TLS, closed administration, unreachable
  backend, no widened permissions, backend source untouched;
- **recovery** (critical): the backup is restored after the configuration and
  the certificate files have been destroyed, the certificate comes back
  **identical** with its key closed, and after a reboot the full recette passes
  with no manual step.

**Read by a reviewer, and not graded here**: the quality of your initial recette
report, and the reasoning written in `explication`. Hypotheses you ruled out
belong in that field: writing them there does not count against you, it is
what a diagnosis is expected to show.

## Good to know before you start

The backend is not yours to change: its code is checked, and the repair of
any incident happens around it, in the proxy or on the system.

The validation destroys, for the recovery test, `/etc/nginx/conf.d` and the
`ssl_certificate` and `ssl_certificate_key` files your configuration loads.
Your backup must therefore cover them, with their permissions.

The test authority loses its root at every restart, by design. The validation
keeps the root it fetched before the reboot and never asks for another renewal
after it: the certificate on disk stays valid against that root.

The time budget is 150 minutes. No hint is given during an assessment session.
