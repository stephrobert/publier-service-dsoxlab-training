# pub-haproxy-confiance

Quatre autorités, deux backends qui portent le même nom, et un HAProxy où
tout répond. C'est le point : les quatre fautes en place ne produisent aucune
erreur visible. Une chaîne de confiance entièrement débranchée ressemble
exactement à une chaîne qui fonctionne.

```bash
dsoxlab run pub-haproxy-confiance
dsoxlab check pub-haproxy-confiance
```
