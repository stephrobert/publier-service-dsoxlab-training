# The task

## The situation

Traefik is already running on `edge.lab`. A small web service is managed by
systemd, but clients cannot reach it through the proxy. The service listens on
port `18081`; the requested public address is `http://systemd.lab.test/`.

## Mission

Publish the host service through Traefik's file provider. Make the route
available and prove that Traefik loads the dynamic configuration without being
restarted.

## What is asked

Route `http://systemd.lab.test/` through the running Traefik instance to the
systemd-managed backend. Traefik already watches `/opt/pub-fichier/dynamic/`.
The check calls the real endpoint and confirms Traefik was not restarted.
