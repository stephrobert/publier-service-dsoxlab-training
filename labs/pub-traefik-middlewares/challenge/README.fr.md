# Défi : comportement des middlewares Traefik

## La situation

Traefik sur `edge.lab` sert déjà un backend local pour
`middleware.lab.test`. Les anciens liens et les requêtes clientes atteignent
actuellement le backend sans les transformations attendues.

## Mission

Faites correspondre les réponses du portail et le comportement des anciennes
URL aux critères du défi. Gardez le backend et le proxy disponibles pendant
l'application de vos changements.

## Ce qui est demandé

Traefik sur `edge.lab` route déjà `middleware.lab.test` vers un backend web
local. Améliorez les réponses sans interrompre le proxy.

### Critères

- les requêtes sous `/portal/` atteignent le backend sans leur préfixe ;
- les requêtes sous `/legacy/` reçoivent une redirection permanente vers le
  chemin correspondant sous `/docs/` ;
- les réponses du portail portent `X-Content-Type-Options: nosniff` et
  `X-Frame-Options: DENY` ;
- les clients qui acceptent gzip reçoivent des réponses compressées ;
- Traefik reste actif sans être redémarré.

Les tests observent les codes HTTP, les en-têtes et le chemin reçu par le
backend, puis confirment que le processus Traefik initial est toujours actif.
Ils n'imposent pas d'organisation particulière des fichiers.
