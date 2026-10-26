# pub-haproxy-sante

HAProxy tourne avec deux serveurs à poids égaux et personne pour les
surveiller : un backend qui tombe reste dans la rotation, et une requête sur
deux part chez lui. Les seuils sont prescrits, parce que la validation mesure
des fenêtres, pas des intentions.

```bash
dsoxlab run pub-haproxy-sante
dsoxlab check pub-haproxy-sante
```
