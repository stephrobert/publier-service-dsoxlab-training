# The task

Make the `whoami` web service on `edge.lab:18080` answer HTTP requests both
before and after the Docker daemon restarts. The tests inspect the container's
restart policy and call the real endpoint after restarting Docker.

The prepared image reference and working directory are described in
`/opt/pub-restart/README`.
