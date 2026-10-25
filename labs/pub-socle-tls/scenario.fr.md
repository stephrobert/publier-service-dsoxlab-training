# Scénario

Quatre points d'accès TLS ont été déployés sur `edge.lab` pour répondre sous le
nom `svc.tls.test`. Avant toute publication, une revue de sécurité demande la
preuve que chaque point d'accès est vraiment ce qu'il prétend être, avec la
racine de confiance de test remise pour cette revue, pas le magasin de
confiance public du système.

## Mission

Lisez `/home/student/README-tls`, connectez-vous à chacun des quatre points
d'accès avec le certificat racine fourni, et écrivez
`/home/student/verdict.yaml` indiquant si chaque point d'accès est accepté et,
quand il est refusé, pourquoi : un nom qui ne correspond pas, une chaîne qui ne
remonte pas à la racine fournie, ou des dates qui placent le certificat hors de
sa période de validité. Ne modifiez pas l'horloge de la machine de test pour
cela.
