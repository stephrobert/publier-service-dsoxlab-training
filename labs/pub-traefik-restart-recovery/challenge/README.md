# The task

## The situation

The web service on `edge.lab` is running in a Docker container, but after the
Docker daemon restarts it stays unavailable until someone intervenes. The
service must recover automatically and answer on `http://edge.lab:18080/`.

## Mission

Make the service available before and after a Docker daemon restart, without
manual intervention.

## What is asked

Make the `whoami` web service on `edge.lab:18080` answer HTTP requests both
before and after the Docker daemon restarts. The tests inspect the container's
restart policy and call the real endpoint after restarting Docker.

The prepared image reference and working directory are described in
`/opt/pub-restart/README`.
