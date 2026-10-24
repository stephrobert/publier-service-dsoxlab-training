# Assessment: publish and recover services

## Criteria

- Two distinct HTTPS services answer from the controller host outside the VM.
- Traefik serves a renewed certificate issued by the running Pebble authority.
- The controller host cannot connect directly to either backend or the
  administration endpoint.
- Both HTTPS services recover after the Docker daemon restarts.
- The assessment is completed within 60 minutes; no hints are provided.

The reference solution is not included in the guides.
