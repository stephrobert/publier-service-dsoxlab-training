# Défi : configurer HTTPS et prouver le renouvellement

Dans `/opt/pub-traefik-acme`, mettez en place Traefik devant le service
`app.lab.test`. Protégez le stockage ACME, redirigez HTTP vers HTTPS et refusez
TLS 1.0 et 1.1.

## Critères

- le fichier de stockage ACME a le mode `0600` ;
- HTTP est redirigé vers HTTPS avec le statut 301 ;
- TLS 1.0 et 1.1 sont refusés ;
- le client rejoint le service en HTTPS et valide le certificat avec la CA
  Pebble fournie ;
- Pebble journalise au moins deux certificats distincts pour le service dans
  le délai du test ;
- Traefik sert au client le dernier certificat émis, valide pour
  `app.lab.test`.

Les tests observent les réponses du client et les journaux de l'autorité. Ils
ne valident pas une configuration particulière ni les fichiers Compose.
