# pub-nginx-cache

Un catalogue est mis en cache derrière Nginx, et mal : le
`Cache-Control` de l'origine est ignoré, la clé ne voit ni la langue
ni la session, et un en-tête `X-Cache-Status: HIT` est ajouté à
toutes les réponses. Appliquez le contrat de contenu.

```bash
dsoxlab run pub-nginx-cache
dsoxlab check pub-nginx-cache
```
