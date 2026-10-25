# pub-traefik-docker

Publish two instances of a web service behind Traefik with the Docker provider:
discovery by labels, nothing exposed by default, no backend port published, and
an instance that can fail with failover measured against the challenge
thresholds. Guide:
https://www.stephane-robert.info/docs/services/reseau/traefik-docker/

```bash
dsoxlab run pub-traefik-docker
dsoxlab check pub-traefik-docker
```
