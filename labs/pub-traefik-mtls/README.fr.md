# pub-traefik-mtls

**Public :** l'apprenant.

Protégez une route Traefik avec du TLS mutuel : le point d'entrée doit
exiger et vérifier un certificat client, et Traefik lui-même doit vérifier
le certificat du backend plutôt que lui faire une confiance aveugle.
Ajoutez une résistance aux en-têtes de transfert forgés et prouvez qu'une
rotation de certificats ne désactive pas silencieusement le contrôle
d'accès.

## Ce que vous saurez faire

- Configurer une option TLS Traefik qui exige et vérifie les certificats
  clients contre une CA.
- Configurer un transport serveur qui vérifie le certificat d'un backend
  contre sa propre CA, sans désactiver la vérification.
- Reconnaître pourquoi les en-têtes d'identité transférés depuis un saut non
  fiable doivent être ignorés.
- Faire tourner des certificats sans rouvrir une brèche dans le contrôle
  d'accès.

Une CA client, une CA backend, des certificats valides et plusieurs
variantes invalides sont préparés. La tâche et les chemins disponibles sont
décrits dans `/opt/pub-mtls/README`.
