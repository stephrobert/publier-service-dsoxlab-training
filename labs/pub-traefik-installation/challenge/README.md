# The task

## The situation

`edge.lab` is a clean machine: the tools are present, but no Traefik instance
from this mission runs yet. `poste.lab` is an independent client on the same
network; it will be the judge of what the entry point really exposes.

## Mission

Install the retained Traefik version under systemd, closed by default:
nothing but the web entrypoint should be reachable from `poste.lab`. Prove
that an invalid dynamic configuration is logged rather than silently
accepted, and that the entry point survives a reboot of `edge.lab`.

## What is asked

Install Traefik under systemd, as the unit `pub-installation-traefik.service`
running the pinned image from `/opt/pub-installation/image-ref`, with the web
entrypoint on port 80 and nothing else reachable. Use the file provider on
`/opt/pub-installation/dynamic` (watch enabled). The check reads the real
container image, probes ports from `poste.lab`, injects an invalid dynamic
file, and reboots `edge.lab` once.
