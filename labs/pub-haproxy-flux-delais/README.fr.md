# pub-haproxy-flux-delais

Toutes les bornes valent la même chose, rien ne distingue une connexion qui
ne répond pas d'une file pleine, les flux longs meurent dans un silence
normal, une réponse perdue est rejouée, et une requête sur deux change
d'instance. Quatre fautes, et le compteur métier est le seul témoin de la
quatrième.

```bash
dsoxlab run pub-haproxy-flux-delais
dsoxlab check pub-haproxy-flux-delais
```
