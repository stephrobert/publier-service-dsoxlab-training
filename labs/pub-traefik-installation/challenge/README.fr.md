# La tâche

Installez Traefik sous systemd, comme unité `pub-installation-traefik.service`
exécutant l'image épinglée de `/opt/pub-installation/image-ref`, avec le point
d'entrée web sur le port 80 et rien d'autre joignable. Utilisez le provider
fichier sur `/opt/pub-installation/dynamic` (watch activé). La notation lit
l'image réelle du conteneur, sonde les ports depuis `poste.lab`, injecte un
fichier dynamique invalide, et redémarre `edge.lab` une fois.
