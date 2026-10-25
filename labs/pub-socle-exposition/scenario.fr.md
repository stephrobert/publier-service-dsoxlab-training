# Scénario

Un service web est publié sur `edge.lab` et répond correctement. Avant la mise
en service, une revue de sécurité constate qu'il a été lancé dans la précipitation :
l'application et son interface d'administration écoutent aussi largement que le
point d'entrée. N'importe qui sur le réseau pourrait contourner le point
d'entrée et leur parler directement.

## Mission

Lisez `/home/student/README-exposition`, découvrez ce qui écoute réellement sur
`edge.lab` et écrivez la matrice de flux dans `/home/student/flux.yaml`. Fermez
ensuite tous les chemins qui contournent le point d'entrée : le service public
reste joignable depuis `poste.lab`, alors que le backend et l'administration ne
le sont que depuis `edge.lab` elle-même.
