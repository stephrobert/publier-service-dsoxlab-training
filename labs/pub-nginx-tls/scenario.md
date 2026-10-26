# Scenario

A local ACME authority runs on the machine, an ACME client is available as
an image, two names must be served over HTTPS, `app.lab.test` and
`api.lab.test`, and **no certificate exists**. Nginx publishes the
application in clear, and already serves the HTTP-01 challenge path.

The bench is described in `/opt/pub-nginx-tls/LISEZ-MOI.txt`.

## Mission

Obtain the certificates, serve both names over HTTPS, protect the keys, and
make the renewal automatic and verifiable.

## What the validation will call, and why

A renewal can be triggered by a systemd timer, by cron, or by a hook of the
ACME client. Requiring one of those would grade an implementation choice
rather than a result.

So provide an executable entry point:

```
/usr/local/bin/renouveler-certificats
```

The validation calls it, then measures the **new serial actually served**.
How you obtain it is up to you.

## Three measured traps

**Pebble's root authority changes on every start.** That is intended by its
authors. It is fetched from `/roots/0`, never assumed, and the test itself
fetches it rather than hard-coding it.

**The HTTP-01 challenge is served in clear, by a `location` placed before
any redirect.** You will often read that a global redirect to HTTPS prevents
validation. That is too strong: Let's Encrypt's validator follows redirects,
up to ten, towards ports 80 and 443, and does not verify the target's
certificate. There, a global redirect often works.

What stays true, and is the reason for the rule: a redirect puts the
challenge outside your control. It makes it depend on what the authority
agrees to follow, and not all do. It fails on the **first** issuance, since
there is nothing to reach on 443 yet. And it breaks as soon as the target
leaves the two allowed ports. Serving the challenge in clear depends only on
your configuration.

**Deleting the ACME account to start over works**, and is exactly what must
not be done: against a real authority, each registration burns a quota and
loses the history. The test compares the account before and after the
renewal.

## What is checked

- **critical**: from `poste.lab`, the client **validates** the chain for
  both names. No `-k`: validation is precisely what is being measured;
- the renewal serves a **new serial**, without restarting the Nginx
  process, and without changing the ACME account;
- **critical**: neither the private keys nor the account are world-readable,
  and the service still answers;
- **critical**: TLS stays correct after a reload, then after a reboot.

The last test cuts the machine, so it runs last.
