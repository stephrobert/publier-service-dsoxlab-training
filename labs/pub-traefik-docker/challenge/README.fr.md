# Publier deux conteneurs derrière Traefik

## La situation

Vous êtes sur `edge.lab`. Dans `/opt/pub-lab`, placez Traefik devant deux
instances du service web `traefik/whoami`, joignable sous le nom
`whoami.lab.test` sur le port 80. Un troisième conteneur, `pub-interne`, tourne
déjà sur le réseau Docker `pub-lab` et doit rester injoignable par Traefik.
`LISEZ-MOI.txt` donne les images (déjà tirées, épinglées par digest) et les
faits sur lesquels les tests s'appuient.

## Mission

Configurez le basculement et les sondes de santé pour que le service reste
utilisable lorsqu'une instance s'arrête ou devient malade :

- à l'arrêt, au plus une erreur est tolérée pendant les 5 premières secondes ;
  ensuite, aucune erreur et aucune requête vers l'instance arrêtée pendant une
  période stable de 5 secondes ;
- si `/health` signale une instance malade, elle doit être retirée de la
  rotation en 5 secondes au plus ; les requêtes restent sans erreur et la
  période stable de 5 secondes ne doit viser que l'autre instance ;
- après redémarrage ou rétablissement, l'instance doit reprendre du trafic en
  moins de 40 secondes.

## Défi : deux instances et un basculement mesurable

Vous travaillez dans `/opt/pub-lab` sur `edge.lab`.

### Ce qui est attendu

1. Traefik répond sur le port 80 de la machine, et `whoami.lab.test` (envoyé en
   en-tête `Host`) atteint les deux instances `traefik/whoami`, qui se partagent
   la charge.
2. Traefik n'expose rien par défaut : un conteneur sans étiquette d'adhésion
   (`pub-interne`) répond 404 à travers lui.
3. Aucun backend ne publie de port sur l'hôte.
4. Lors de l'arrêt d'une instance, au plus une erreur est tolérée pendant les
   5 premières secondes. Ensuite, aucune erreur ni requête vers cette instance
   pendant 5 secondes stables. Elle reprend du trafic en moins de 40 secondes
   après son redémarrage.
5. Une instance qui se déclare malade sur `/health` est retirée de la rotation
   en 5 secondes au plus. Les requêtes restent sans erreur ; pendant les
   5 secondes stables suivantes, seul l'autre backend reçoit du trafic.
   L'instance reprend du trafic en moins de 40 secondes après son rétablissement.

### Ce qui est prouvé

Les tests envoient des requêtes comme un client, arrêtent et rendent malade une
instance eux-mêmes, puis la restaurent. Ils lisent ce que la machine publie,
jamais votre Compose.
