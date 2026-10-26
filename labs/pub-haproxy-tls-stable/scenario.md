# Scenario

The application is published over HTTP on port 80, and that is all. There is
no certificate, no `bind ssl`, and **no route for the ACME challenge**.

Provided:

- a test certificate authority, issuing certificates valid for **five
  minutes** so that renewal is observable right away;
- an **external ACME client**, wrapped in an executable so you can call it
  without ceremony. Its challenge server already listens on the loopback;
  what is missing is the route that takes the challenge to it;
- that authority's root, so your checks can be strict.

Everything is described in `/opt/pub-haproxy-tls-stable/recette.txt`.

## Mission

Serve both names over HTTPS, **each with its own certificate**, and deliver a
`renouveler` script that performs the whole cycle.

A single certificate carrying both names as SANs does not answer the recipe.
The lab is about SNI selection, and two distinct certificates are the only way
to measure it: the counter-test presents one name's certificate and validates
it against the other, which must fail.

## The four checks

1. **Both names validate strictly.** Chain and hostname, against the
   authority's root, never with verification disabled. The counter-test is the
   half that matters: a certificate covering both names would pass strict
   verification on both sides, and the counter-test would refuse it. This
   check is critical.

2. **The cycle produces a new certificate.** The validation **runs your
   script** `renouveler`, then compares the serial number and expiry actually
   served before and after. A cycle is not observed afterwards: it is played.

   Second half: the validation itself pushes a **deliberately invalid**
   certificate through the runtime socket and requires it to be **refused**,
   the service still presenting the previous one. That is what separates a
   verified load from a load: HAProxy checks the material before putting it
   into service, and refuses rather than falling.

3. **Keys and account are protected, and absent from outputs.** Any file
   carrying a private key must be unreadable by others, and no key may appear
   in the logs or in the system journal. This check is critical: a key in a
   log is a published key, and rotation does not catch up with it.

4. **The cycle still works after a reload then a reboot.** Both events are
   played, and renewal is **replayed after the reboot**. This check is
   critical and comes last, since it cuts the machine. A cycle that depended
   on a directory under `/run` or on an environment variable of your shell
   shows up there, and nowhere earlier.
