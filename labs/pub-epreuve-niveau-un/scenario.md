# Scenario

You are on the change window for a small web platform. Two services must be
published through one Traefik entry point. The ACME test authority and backend
images are available on the machine.

## Mission

Publish both services over HTTPS with automatically renewed certificates.
Verify that an external client can reach the services but cannot connect
directly to either backend or the administration endpoint. Configure Docker
restart recovery and prove both services return after the daemon restarts.

This is a 60-minute assessment. Hints are disabled. The final check makes
requests from the controller host outside the VM, observes certificate
issuance and renewal, tests the blocked ports, and restarts Docker.
