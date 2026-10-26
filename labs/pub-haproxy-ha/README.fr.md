# pub-haproxy-ha

Deux points d'entrée servent le même service avec le même certificat, et
rien n'en fait un seul. Déployez la bascule, puis perdez un processus et
un hôte pendant que le client interroge toujours la même adresse.

```bash
dsoxlab run pub-haproxy-ha
dsoxlab check pub-haproxy-ha
```
