# pub-traefik-installation

**Public :** l'apprenant.

Installez un point d'entrée Traefik comme un opérateur le garderait : une
version vérifiable, fermé par défaut, un mode d'échec exploitable, et un cycle
de vie qui survit à un redémarrage.

## Ce que vous saurez faire

- Faire tourner Traefik sous systemd et vérifier la version réellement exécutée.
- Ne laisser écouter que le port prévu, vérifié depuis un client indépendant.
- Lire la réaction de Traefik à une configuration dynamique invalide.
- Prouver que le point d'entrée revient après le redémarrage de la machine.

Le répertoire de travail et ses chemins sont décrits dans
`/opt/pub-installation/README`.
