# pub-epreuve-socle

**Audience:** the learner.

This is the socle's final assessment. No template to copy from: a service,
`epreuve.test` on `edge.lab`, is already running when you arrive, carrying
a business value and a backup of it. You did not set it up. An incident,
not announced, has been layered on top of it after the fact.

## What you will be able to do

- Produce an architecture dossier for a service you did not build:
  its names, its flows, the identities involved, and who is responsible
  for what, read from observation rather than recited from memory.
- Prove the service works from an independent client, with data you did
  not choose in advance, under strict TLS validation, without ever
  weakening that validation to get an answer.
- Diagnose and repair an unannounced incident on a layer you are not told
  in advance, and show your reasoning rests on what you actually observed.
- Execute a restore from the backup already in place and show the result
  is trustworthy: the right configuration, the right data, and a
  certificate chain that still validates strictly afterward.
