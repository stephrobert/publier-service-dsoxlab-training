# pub-haproxy-routage

HAProxy tourne, quatre backends sont sains, et le routage est faux de quatre
façons : l'ordre des règles, un préfixe qui se fait passer pour un chemin, une
route vers ce qui n'est pas déployé, et un backend par défaut qui attrape tout
nom inconnu. Chaque backend compte les requêtes qu'il sert : une route qui
fuit ne peut donc pas se cacher derrière une réponse plausible.

```bash
dsoxlab run pub-haproxy-routage
dsoxlab check pub-haproxy-routage
```
