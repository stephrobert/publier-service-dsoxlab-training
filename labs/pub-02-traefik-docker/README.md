# pub-02-traefik-docker

Publish two instances of a web service behind Traefik with the Docker provider:
discovery by labels, nothing exposed by default, no backend port published, and
an instance that can fail without a client error. Guide:
https://www.stephane-robert.info/docs/services/reseau/traefik-docker/

```bash
dsoxlab run pub-02-traefik-docker
dsoxlab check pub-02-traefik-docker
```
