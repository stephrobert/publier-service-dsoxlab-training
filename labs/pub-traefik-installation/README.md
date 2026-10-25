# pub-traefik-installation

**Audience:** the learner.

Install a Traefik entry point the way an operator would keep it: a verifiable
version, closed by default, a usable failure mode, and a cycle of life that
survives a reboot.

## What you will be able to do

- Run Traefik under systemd and verify the version actually executed.
- Keep only the intended port listening, checked from an independent client.
- Read Traefik's reaction to an invalid dynamic configuration.
- Prove the entry point comes back after the machine reboots.

The working directory and its paths are described in
`/opt/pub-installation/README`.
