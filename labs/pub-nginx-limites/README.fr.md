# pub-nginx-limites

Appliquez des limites par route avec une clé que l'appelant ne peut pas
forger, répondez 429 plutôt que 503, et gardez la route publique hors
de la pénalité de l'administration.

```bash
dsoxlab run pub-nginx-limites
dsoxlab check pub-nginx-limites
```
