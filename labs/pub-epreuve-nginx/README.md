# pub-epreuve-nginx

**Audience:** the learner.

This is the final assessment of the Nginx module. No template to copy from:
you are handed an empty Nginx, a static site, an API and a local ACME
authority, and you publish and operate the service under two names. An
incident, not announced, is injected after your initial recette.

## What you will be able to do

- Publish a static site and an API under two names, with a strict HTTPS chain
  and a renewal that really renews, without ever weakening validation.
- Close the administration and the backend, refuse what the service does not
  use, and cache public answers without ever mixing two sessions.
- Deliver a long stream at the backend's rhythm, log durations that measure,
  and raise an alert that fires and falls back.
- Diagnose and repair an unannounced incident without losing a guarantee.
- Prove a recovery plan: restore from a backup, reboot, replay the recette.

```bash
dsoxlab run pub-epreuve-nginx
dsoxlab check pub-epreuve-nginx
```
