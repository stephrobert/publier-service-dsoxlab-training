# Scenario

The stack was healthy. A fault was injected, drawn at random among five
families: routing, the health probe, backend TLS trust, a traffic limit, or
saturation. **You do not know which one.**

Noise was laid on top, and it explains nothing: a frontend for an abandoned
name, an operations notes file, a server declared broken on purpose. Reading
`/etc/haproxy/notes-exploitation.txt` is part of the job.

The recipe describes the expected healthy state:
`/opt/pub-haproxy-depannage/recette.txt`.

## Two canaries, and they are part of the healthy state

This is the most important point of this lab.

- **`/api-usurpe/`** leads to a backend whose certificate is signed by a
  foreign authority and which carries **the same name** as the legitimate
  one. It serves the same marker. It must **stay refused**: its refusal is
  the proof that backend TLS verification is strict.

- **`sonde-cassee`** is a live server whose readiness fails permanently and
  whose useful routes return 500. It must **stay out of service**.

Neither is part of the fault. Disabling them, one by removing
`verify required`, the other by removing the probes, would bring the service
back and remove the guarantee at the same time. That is exactly what the
third check measures, and it is the temptation of every three-in-the-morning
call.

## The four checks

1. **The dossier names the cause and tells it apart from its symptom.** A
   503 is not a cause: it is what the proxy answers when it has no server
   left, and at least three of the five families produce it. A human reads
   the dossier; the test only checks that it exists and separates the two.

2. **The service and the healthy routes are restored.** The matrix is
   replayed from the independent client, with a token per measurement.

3. **Verifications are not disabled.** Critical check: both canaries must
   hold their role **after** your fix.

4. **Administration and backends stay unreachable.** Critical too, and
   measured in both directions: none of it answers from the client, and all
   of it answers from the machine.
