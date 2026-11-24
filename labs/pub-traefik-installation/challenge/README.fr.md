# La tâche

## La situation

`edge.lab` est une machine propre : les outils sont présents, mais aucune
instance Traefik de cette mission ne tourne encore. `poste.lab` est un client
indépendant sur le même réseau ; c'est lui qui jugera ce que le point d'entrée
expose réellement.

## Mission

Installez la version retenue de Traefik sous systemd, fermée par défaut :
seul le point d'entrée web doit être joignable depuis `poste.lab`. Prouvez
qu'une configuration dynamique invalide est journalisée plutôt qu'acceptée en
silence, et que le point d'entrée survit à un redémarrage de `edge.lab`.

## Ce qui est demandé

Installez Traefik sous systemd, comme unité `pub-installation-traefik.service`
exécutant l'image épinglée de `/opt/pub-installation/image-ref`, avec le point
d'entrée web sur le port 80 et rien d'autre joignable. Utilisez le provider
fichier sur `/opt/pub-installation/dynamic` (watch activé). La notation lit
l'image réelle du conteneur, sonde les ports depuis `poste.lab`, injecte un
fichier dynamique invalide, et redémarre `edge.lab` une fois.
