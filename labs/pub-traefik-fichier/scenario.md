# Scenario

Traefik is already running on `edge.lab`. A small web service is managed by
systemd, but clients cannot reach it through the proxy. The service listens on
port `18081`; the requested public address is `http://systemd.lab.test/`.

## Mission

Publish the host service through Traefik's file provider. Make the route
available and prove that Traefik loads the dynamic configuration without being
restarted.
