# Challenge: upgrade and roll back Traefik

Upgrade the provided proxy from v3.7.6 to v3.7.15 without losing the service
configuration. Keep a rollback path to the previous pinned image.

## Criteria

- The running proxy uses the pinned v3.7.15 image and reports that version.
- `upgrade.lab.test` returns HTTP 200 from the expected backend.
- A rollback to the pinned v3.7.6 image succeeds, and the upgraded version is
  restored afterward.

The final check briefly switches versions to prove the rollback path, then
returns the proxy to v3.7.15. The reference solution is not included in the
guides.
