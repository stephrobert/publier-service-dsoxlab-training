# La tâche

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
