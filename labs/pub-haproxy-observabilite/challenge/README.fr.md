# Défi : observer HAProxy avec Prometheus

## Critères

- L'application reste disponible derrière HAProxy.
- Prometheus collecte les métriques HAProxy et indique que le backend est sain.
- L'exporteur est joignable depuis la VM, mais pas depuis une autre machine.
- L'interface web Prometheus n'est pas exposée aux autres machines.

Le corrigé de référence ne figure pas dans les guides.
