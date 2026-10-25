# Scénario

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
