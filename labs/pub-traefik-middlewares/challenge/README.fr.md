# Défi : comportement des middlewares Traefik

Traefik sur `edge.lab` route déjà `middleware.lab.test` vers un backend web
local. Améliorez les réponses sans interrompre le proxy.

## Critères

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
