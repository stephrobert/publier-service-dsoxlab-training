# La tâche

## La situation

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

## Ce qui est demandé

Corrigez `/opt/pub-mtls/dynamic/routes.yaml` : passez `clientAuthType` à
`RequireAndVerifyClientCert` sur l'option TLS `mtls` pour qu'un certificat
client signé par la CA client soit réellement exigé et vérifié ; passez
`insecureSkipVerify` à `false` et ajoutez `rootCAs: [backend-ca.crt]` sur le
transport serveur `verif-backend` pour que Traefik vérifie le certificat du
backend lui-même au lieu de lui faire une confiance aveugle. Corrigez
ensuite `/opt/pub-mtls/traefik-static.yaml` : restreignez
`entryPoints.websecure.forwardedHeaders.trustedIPs` à la seule adresse du
reverse proxy amont autorisé (`172.30.10.10/32`), et redémarrez Traefik
(`docker restart pub-mtls-traefik`) puisqu'il s'agit d'un réglage statique.
Les contrôles appellent le véritable point d'entrée HTTPS sur le port 8443
(clients directs) et le proxy autorisé sur le port 8080 (clients
indirects), et font tourner la CA client à chaud pour confirmer que le
contrôle d'accès y survit.
