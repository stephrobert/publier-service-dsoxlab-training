# Configurer HTTPS et ACME dans Traefik

## La situation

Vous administrez `edge.lab`. Le service `app.lab.test` doit être disponible
derrière Traefik en HTTPS. Une autorité ACME de test est déjà lancée sur la
machine et remet des certificats de courte durée afin que le renouvellement
puisse être observé dans le temps d'un exercice.

## Mission

Configurez Traefik pour obtenir et renouveler automatiquement le certificat
ACME de `app.lab.test`, sans intervention manuelle après le démarrage. Les
requêtes HTTP doivent être redirigées vers HTTPS, le stockage ACME doit être
protégé et les anciennes versions du protocole TLS doivent être refusées.

La preuve ne se limite pas à un certificat présent dans le stockage : le
fichier doit avoir des permissions strictes, le journal de l'autorité doit
montrer au moins deux émissions distinctes et un client HTTPS doit recevoir le
certificat renouvelé, valide pour le bon nom et émis par l'autorité de cette
session.

Le répertoire `/opt/pub-traefik-acme/LISEZ-MOI.txt` décrit les services déjà
disponibles et les contraintes du poste.

## Défi : configurer HTTPS et prouver le renouvellement

Dans `/opt/pub-traefik-acme`, mettez en place Traefik devant le service
`app.lab.test`. Protégez le stockage ACME, redirigez HTTP vers HTTPS et refusez
TLS 1.0 et 1.1.

### Critères

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
