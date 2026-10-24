# Publier deux conteneurs derrière Traefik

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
