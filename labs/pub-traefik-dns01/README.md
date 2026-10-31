# pub-traefik-dns01

Obtain a wildcard certificate through Traefik with the ACME DNS-01 challenge,
give the automation an identity limited to its zone, and prove that the
temporary records are removed.

Guide: https://www.stephane-robert.info/docs/services/web/certificats-acme/

```bash
dsoxlab run pub-traefik-dns01
dsoxlab check pub-traefik-dns01
```
