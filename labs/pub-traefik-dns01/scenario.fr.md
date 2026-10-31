# Émettre un joker avec DNS-01

Vous administrez `edge.lab`. La boutique publie chaque semaine de nouveaux
sous-domaines de `boutique.lab.test`, et l'équipe ne veut plus demander un
certificat par nom. Il lui faut un **certificat joker** `*.boutique.lab.test`,
servi par Traefik, et l'autorité n'en délivre un qu'à travers le défi ACME
**DNS-01** : il faut prouver qu'on contrôle la zone en y publiant un
enregistrement TXT.

Le banc tourne sans Internet. Une autorité ACME de test, Pebble, lit les TXT
sur un serveur DNS faisant autorité de test. Ce serveur ne s'administre pas
directement : on passe par l'API d'un fournisseur DNS, comme chez un vrai
hébergeur. On vous en a remis le compte administrateur, qui détient toutes les
zones.

## Mission

Obtenez le joker par Traefik, servi à n'importe quel nom de
`boutique.lab.test`, sans intervention manuelle après le démarrage.
L'automatisation qui publie le défi ne doit pas recevoir les clés de tout le
DNS : donnez-lui une identité limitée à sa propre zone. Les enregistrements
temporaires doivent disparaître une fois le défi joué.

`/opt/pub-traefik-dns01/LISEZ-MOI.txt` décrit le banc, et
`/home/student/fournisseur-dns-admin.txt` le compte du fournisseur.
