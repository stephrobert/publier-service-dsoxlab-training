# Scénario

Traefik sur `edge.lab` expose une application sensible en HTTPS. L'option
TLS du point d'entrée accepte actuellement n'importe quelle connexion,
certificat client ou non : qui atteint le port entre. De l'autre côté,
Traefik parle au backend en HTTPS aussi, mais lui fait confiance sans
vérifier son certificat du tout, si bien qu'un backend présentant le
mauvais certificat passerait inaperçu. Un reverse proxy placé devant
celui-ci est autorisé à transférer des en-têtes d'identité, mais rien
n'empêche un appelant direct et non fiable de forger les mêmes en-têtes.

## Mission

Exigez un certificat client valide signé par la CA client du lab avant que
Traefik n'accepte une connexion ; rejetez les certificats absents,
étrangers ou expirés. Faites vérifier à Traefik le certificat du backend
contre la CA backend du lab au lieu de sauter la vérification, pour qu'un
mauvais certificat côté backend soit détecté. Assurez-vous que des en-têtes
de transfert forgés par un appelant direct non fiable ne changent pas
l'identité retenue par Traefik, tandis que les en-têtes du reverse proxy
amont autorisé du lab continuent d'être pris en compte. Enfin, faites
tourner les certificats et prouvez que le contrôle d'accès tient toujours.
