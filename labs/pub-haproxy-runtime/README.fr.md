# pub-haproxy-runtime

Un seul socket, en mode admin, ouvert au monde, et aucun fichier d'état.
N'importe quel compte de la machine peut sortir un serveur du service, et le
prochain rechargement oublie toute décision prise à chaud. Rien n'est cassé,
et c'est pour cela que personne ne regarde.

```bash
dsoxlab run pub-haproxy-runtime
dsoxlab check pub-haproxy-runtime
```
