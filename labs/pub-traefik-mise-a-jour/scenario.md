# Scenario

The change window is open. The reverse proxy runs Traefik v3.7.6, and users
report that the published service is unavailable. Review the live version,
configuration, and release notes before changing the deployment.

## Mission

Upgrade to Traefik v3.7.15 using the pinned image, restore the intended route,
and verify the response from the running service. Keep a rollback definition
for the known-good version. The automated check will execute the rollback,
verify the older version is serving, and restore the upgraded version.

The upgrade stays within Traefik v3. The v2-to-v3 migration guide is useful
background for a future major-version migration, but those breaking changes
are not part of this patch-level upgrade.
