# Défi : un joker par DNS-01, avec une identité limitée

Dans `/opt/pub-traefik-dns01`, mettez en place Traefik devant un service
répondant à tout nom de `boutique.lab.test`, avec un certificat joker obtenu
par le défi ACME DNS-01 auprès de l'autorité de test.

## Critères

- un nom de `boutique.lab.test` tiré au hasard répond en HTTPS sous
  vérification stricte, avec le joker `*.boutique.lab.test` émis par
  l'autorité de cette session ;
- le défi a été publié par le fournisseur DNS du banc ;
- le compte qui l'a publié n'est pas `admin`, n'a que la zone
  `boutique.lab.test`, et se voit refuser une publication hors de cette zone ;
- l'autorité de test est celle que le banc a posée : la résoudre ne passe pas
  par l'affaiblir ;
- chaque enregistrement de défi publié a été retiré ensuite.

Les tests observent le certificat servi, le journal du fournisseur et
l'empreinte de la plateforme. Ils ne valident ni une configuration
particulière ni les fichiers Compose.
