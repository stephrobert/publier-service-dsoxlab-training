# pub-haproxy-installation

HAProxy est installé et arrêté, avec une configuration qui ne porte aucun
listener. Publiez ce que le manifeste décrit, puis montrez qu'un frontend HTTP
et un relais TCP ne sont pas la même chose : le premier comprend des requêtes,
le second ne fait que déplacer des octets.

```bash
dsoxlab run pub-haproxy-installation
dsoxlab check pub-haproxy-installation
```
