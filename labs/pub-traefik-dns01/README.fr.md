# pub-traefik-dns01

Obtenir par Traefik un certificat joker avec le défi ACME DNS-01, en donnant à
l'automatisation une identité limitée à sa zone, et prouver que les
enregistrements temporaires sont retirés.

Guide : https://www.stephane-robert.info/docs/services/reseau/traefik-tls-acme/

```bash
dsoxlab run pub-traefik-dns01
dsoxlab check pub-traefik-dns01
```
