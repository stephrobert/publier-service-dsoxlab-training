# Scenario

`edge.lab` is a clean machine: the tools are present, but no Traefik instance
from this mission runs yet. `poste.lab` is an independent client on the same
network; it will be the judge of what the entry point really exposes.

## Mission

Install the retained Traefik version under systemd, closed by default:
nothing but the web entrypoint should be reachable from `poste.lab`. Prove
that an invalid dynamic configuration is logged rather than silently
accepted, and that the entry point survives a reboot of `edge.lab`.
