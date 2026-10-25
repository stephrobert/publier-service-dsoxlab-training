# pub-socle-application

**Public :** l'apprenant.

Apprenez pourquoi « ça marche en curl » n'est pas la même question que
« ça marche dans un navigateur ». Un reverse proxy qui ne retransmet pas
le schéma qu'il a lui-même terminé, une application qui cantonne son
cookie de session à un domaine que personne n'a demandé, une politique
CORS qui dit oui à tout le monde parce que dire non aux bonnes personnes
semblait plus compliqué, et un en-tête d'identité encore fait confiance
depuis le client : rien de tout cela n'est visible à un outil qui
n'applique pas la politique de même origine, ne stocke pas les cookies par
domaine, et ne suit pas une chaîne de redirection jusqu'à son terme.

## Ce que vous saurez faire

- Lire un parcours de connexion comme une chaîne de redirections avec un
  schéma, une autorité et un nombre borné de sauts, et reconnaître une
  boucle causée par un proxy qui tait silencieusement le schéma qu'il a
  lui-même terminé.
- Cantonner correctement un cookie de session, et le vérifier de la seule
  façon qui compte : en l'utilisant réellement dans un navigateur, pas en
  lisant un en-tête de réponse et en supposant qu'il sera accepté.
- Distinguer une origine autorisée de toute origine, et le prouver avec un
  vrai pré-vol et une vraie requête inter-origines, pas un en-tête curl
  qui n'applique jamais rien.
- Expliquer pourquoi un reverse proxy doit calculer une identité à partir
  d'une session validée au lieu de reconduire l'en-tête d'identité déjà
  porté par le client, et montrer qu'un en-tête forgé n'accorde plus rien
  une fois corrigé.

Vos observations se passent sur `edge.lab`, avec le navigateur
automatisable fourni ; `challenge/README.md` décrit la tâche précisément.
