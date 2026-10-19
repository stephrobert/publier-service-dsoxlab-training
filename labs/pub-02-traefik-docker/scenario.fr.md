# Publier deux conteneurs derrière Traefik

Vous êtes sur `edge.lab`. Dans `/opt/pub-lab`, placez Traefik devant deux
instances du service web `traefik/whoami`, joignable sous le nom
`whoami.lab.test` sur le port 80. Un troisième conteneur, `pub-interne`, tourne
déjà sur le réseau Docker `pub-lab` et doit rester injoignable par Traefik.
`LISEZ-MOI.txt` donne les images (déjà tirées, épinglées par digest) et les
faits sur lesquels les tests s'appuient.

## Mission

Un client doit pouvoir utiliser le service pendant qu'une des deux instances est
arrêtée ou malade, sans jamais recevoir d'erreur.
