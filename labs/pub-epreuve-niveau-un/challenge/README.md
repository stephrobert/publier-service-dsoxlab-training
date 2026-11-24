# Assessment: publish and recover services

## The situation

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

## What is asked

### Criteria

- Two distinct HTTPS services answer from the controller host outside the VM.
- Traefik serves a renewed certificate issued by the running Pebble authority.
- The controller host cannot connect directly to either backend or the
  administration endpoint.
- Both HTTPS services recover after the Docker daemon restarts.
- The assessment is completed within 60 minutes; no hints are provided.

The reference solution is not included in the guides.
