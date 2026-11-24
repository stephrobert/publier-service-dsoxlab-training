# La tâche

## La situation

Le site `shop.pub.test` tourne en version v1. La version v2 est prête sur
d'autres adresses et doit passer en production. La dernière fois, la moitié des
utilisateurs a continué d'arriver sur l'ancienne version pendant une heure après
le changement. On vous demande de faire la bascule proprement, et de pouvoir
revenir en arrière immédiatement si la v2 se comporte mal.

## Mission

Lisez `/home/student/README-dns`, puis produisez sur `edge.lab` :

- `/home/student/dns.yaml`, les faits que vous avez trouvés sur la zone ;
- `/home/student/basculer.sh`, un script qui fait pointer `shop.pub.test` vers
  une version donnée et rend le changement visible rapidement par les clients.

Le site est vérifié depuis `poste.lab`, à travers le résolveur à cache, comme
le ferait un utilisateur.

## Ce qui est demandé

1. Écrivez `/home/student/dns.yaml` :

```yaml
serveur_autoritaire: <adresse du serveur qui fait autorité sur pub.test>
ttl_initial: <TTL en secondes des enregistrements shop avant toute modification>
types_a_basculer: [<types d'enregistrement à changer pour passer shop en v2>]
```

2. Écrivez `/home/student/basculer.sh`, lancé sur `edge.lab` par
   `bash basculer.sh <v1|v2>`. Il doit faire pointer `shop.pub.test` vers la
   version demandée en IPv4 comme en IPv6, et la rendre visible des clients en
   quelques secondes (pas après le TTL d'origine). Il doit refonctionner au
   second appel, dans un sens comme dans l'autre.

Les tests appellent votre script eux-mêmes, dans les deux sens, puis récupèrent
`http://shop.pub.test/` depuis `poste.lab` en IPv4 et en IPv6 pour savoir quelle
version répond. Le site doit finir en v2.
