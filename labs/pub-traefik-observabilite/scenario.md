# Scenario

Traefik on `edge.lab` already routes `observabilite.lab.test` to a local
systemd-managed backend. A local Prometheus instance is also running, but the
proxy is not yet observable and the 5xx alert is missing.

## Mission

Instrument the proxy and configure a useful alert without exposing monitoring
endpoints to the network.
