# pub-socle-cache-delais

Corrigez une politique de cache et de délais rapide et dangereuse : elle
peut mélanger deux utilisateurs, doubler une commande, et laisser un backend
mort retenir tous les appelants.

```bash
dsoxlab run pub-socle-cache-delais
dsoxlab check pub-socle-cache-delais
```
