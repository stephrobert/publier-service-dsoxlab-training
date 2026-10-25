# The task

Install Traefik under systemd, as the unit `pub-installation-traefik.service`
running the pinned image from `/opt/pub-installation/image-ref`, with the web
entrypoint on port 80 and nothing else reachable. Use the file provider on
`/opt/pub-installation/dynamic` (watch enabled). The check reads the real
container image, probes ports from `poste.lab`, injects an invalid dynamic
file, and reboots `edge.lab` once.
