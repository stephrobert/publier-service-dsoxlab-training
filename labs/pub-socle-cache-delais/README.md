# pub-socle-cache-delais

Fix a cache and timeout policy that is fast and dangerous: it can mix two
users up, duplicate an order, and let a dead backend hold every caller.

```bash
dsoxlab run pub-socle-cache-delais
dsoxlab check pub-socle-cache-delais
```
