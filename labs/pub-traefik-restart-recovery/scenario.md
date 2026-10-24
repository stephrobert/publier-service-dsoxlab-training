# Scenario

The web service on `edge.lab` is running in a Docker container, but after the
Docker daemon restarts it stays unavailable until someone intervenes. The
service must recover automatically and answer on `http://edge.lab:18080/`.

## Mission

Make the service available before and after a Docker daemon restart, without
manual intervention.
