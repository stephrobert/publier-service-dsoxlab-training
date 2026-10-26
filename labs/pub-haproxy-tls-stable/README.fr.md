# pub-haproxy-tls-stable

L'application est publiée en HTTP, et rien de plus : aucun certificat, aucun
`bind ssl`, aucune route pour le défi ACME. Une autorité de test et un client
ACME externe sont fournis. La validation exécute votre script de
renouvellement au lieu d'inspecter son résultat, parce qu'un cycle ne se
constate pas après coup.

```bash
dsoxlab run pub-haproxy-tls-stable
dsoxlab check pub-haproxy-tls-stable
```
