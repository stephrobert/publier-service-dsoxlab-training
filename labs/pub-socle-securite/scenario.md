# Scenario

A service publishes three routes: `/` is public, `/compte` is for a
logged-in user, `/admin` for administration. They are served by a
configurable guard, which applies
`/opt/pub-socle-securite/politique.yaml` to the letter.

That policy is **empty**. The guard therefore applies it faithfully:
everything goes through, every identity header is believed, and the log
keeps whatever it receives, credentials included.

The test identities are in `/home/student/identites.txt`.

## Mission

Write the policy. It must let legitimate traffic through, refuse the others
on sensitive routes, resist bypassing, and stop writing secrets to disk.

## What is checked, and why never a directive

A policy is judged on what the service **answers**, not on what it declares:
a file can name a rule the guard applies to nothing, because it targets a
prefix no route matches. The validation therefore sends real requests from
`poste.lab`, the independent client, and reads the **status** and the
**body**.

Reading the body is not a luxury. A 200 returning the public page on
`/admin` is not a leak; a 200 returning "revocation des acces" is. The
status alone does not tell them apart.

Four checks, three of them critical:

1. **The legitimate goes through.** The three allowed categories get their
   content. This is the anchor: refusing everyone would satisfy the other
   three checks by removing the service.
2. **Sensitive routes refuse**, and the body of the refusal does not carry
   the protected content.
3. **Neither direct origin nor a forged header bypasses.** The application
   still answers on its port from the client network: a policy placed in
   front of a door you can walk around protects nothing. And an `X-Identite`
   sent by the caller itself is not an identity.
4. **No seeded secret survives.** The validation sends a sentinel value in
   `Cookie` and `Authorization`, then looks for it in the log and in the
   dossier. It also checks the log is not empty: redacting is not the same
   as logging nothing.

## Hints

- The guard re-reads the policy on every request: no restart is needed to
  see it act.
- Two gestures close direct access, and both are accepted: bind the
  application to the loopback interface, or refuse its port from outside.
- `proxys_de_confiance` is what separates a header set by a legitimate proxy
  from one forged by anybody.
