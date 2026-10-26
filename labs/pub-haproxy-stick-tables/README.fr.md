# pub-haproxy-stick-tables

Une stick-table est déjà en place. Elle se remplit, elle se lit très bien
dans `show table`, et elle ne protège de rien : sa clé est un en-tête que le
client envoie, son seuil n'est jamais atteint, et sa fenêtre et son
expiration sont le même nombre. Tout a l'air de fonctionner.

```bash
dsoxlab run pub-haproxy-stick-tables
dsoxlab check pub-haproxy-stick-tables
```
