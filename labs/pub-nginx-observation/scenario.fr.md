# Scénario

Nginx publie déjà l'application, mais un seul client peut la submerger de
requêtes, le journal d'accès est un texte brut impossible à filtrer, et rien
ne permet de lire les compteurs de connexions du proxy.

## Mission

Limitez le débit des requêtes par adresse cliente : une rafale reçoit `429`,
une requête normale reçoit toujours `200`. Écrivez le journal d'accès à raison
d'un objet JSON par ligne dans `/opt/pub-nginx-observation/logs/access.log`,
avec les champs `time`, `remote_addr`, `request_uri`, `status` et
`request_time`. Exposez `stub_status` sur `127.0.0.1:8081` uniquement, sans
ouvrir ce port au réseau.
