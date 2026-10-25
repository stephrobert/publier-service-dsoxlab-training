# La tâche

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
