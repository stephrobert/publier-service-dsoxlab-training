# Configurer HTTPS et ACME dans Traefik

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
