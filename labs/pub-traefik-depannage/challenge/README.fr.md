# Défi : diagnostiquer et réparer Traefik

Cinq pannes sont injectées dans des routes Traefik indépendantes. Inspectez
les journaux du proxy et des accès avant de modifier la configuration du
fournisseur fichier.

## Critères

- `notfound.lab.test` répond HTTP 200 au lieu de 404.
- `badgateway.lab.test` répond HTTP 200 au lieu de 502.
- `timeout.lab.test/slow` répond HTTP 200 au lieu de 504.
- Le certificat servi pour `tls.lab.test` contient cet hôte dans ses noms
  alternatifs du sujet.
- `loop.lab.test` atteint le backend via la redirection HTTP vers HTTPS sans
  boucle.
- Traefik applique les changements dynamiques sans être redémarré.

Les tests vérifient les réponses HTTP réelles, le certificat présenté par le
proxy et la séquence de redirection. Les guides ne contiennent pas le corrigé.
