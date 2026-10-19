# Défi : deux instances, un point d'entrée, aucune panne visible

Vous travaillez dans `/opt/pub-lab` sur `edge.lab`.

## Ce qui est attendu

1. Traefik répond sur le port 80 de la machine, et `whoami.lab.test` (envoyé en
   en-tête `Host`) atteint les deux instances `traefik/whoami`, qui se partagent
   la charge.
2. Traefik n'expose rien par défaut : un conteneur sans étiquette d'adhésion
   (`pub-interne`) répond 404 à travers lui.
3. Aucun backend ne publie de port sur l'hôte.
4. Pendant qu'une instance est arrêtée, un client qui envoie des requêtes en
   boucle ne reçoit aucune erreur. À son retour, elle reprend du trafic.
5. Une instance qui tourne toujours mais se déclare malade sur `/health` ne
   reçoit plus de trafic, sans erreur non plus.

## Ce qui est prouvé

Les tests envoient des requêtes comme un client, arrêtent et rendent malade une
instance eux-mêmes, puis la restaurent. Ils lisent ce que la machine publie,
jamais votre Compose.
