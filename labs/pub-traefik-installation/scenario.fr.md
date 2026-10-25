# Scénario

`edge.lab` est une machine propre : les outils sont présents, mais aucune
instance Traefik de cette mission ne tourne encore. `poste.lab` est un client
indépendant sur le même réseau ; c'est lui qui jugera ce que le point d'entrée
expose réellement.

## Mission

Installez la version retenue de Traefik sous systemd, fermée par défaut :
seul le point d'entrée web doit être joignable depuis `poste.lab`. Prouvez
qu'une configuration dynamique invalide est journalisée plutôt qu'acceptée en
silence, et que le point d'entrée survit à un redémarrage de `edge.lab`.
