# Scenario

Une petite application a été déployée derrière un point d'entrée TLS sur
`edge.lab`, le tout en `127.0.0.1` (le navigateur automatisable tourne sur
le même hôte). La configuration livrée porte quatre erreurs à la fois : le
parcours de connexion boucle indéfiniment au lieu d'aboutir sur la page de
compte, le cookie de session est cantonné à un domaine qu'aucun navigateur
n'acceptera jamais, la politique d'origine répond oui à toute origine, et
le point d'entrée répète encore l'en-tête d'identité envoyé par le client
au lieu de le décider à partir d'une session validée.

## Mission

Lisez `/home/student/README-app`, puis modifiez
`/etc/pub-app/politique.yaml` (relu à chaque requête, aucun redémarrage
nécessaire) pour que :

- le parcours de connexion se termine sur la page de compte en HTTPS sans
  boucler ;
- la session légitime, une fois utilisée dans le navigateur, affiche le
  compte comme connecté ;
- l'origine partenaire puisse lire la réponse de l'API, l'origine intruse
  ne le puisse pas, les deux vérifiées depuis un vrai navigateur ;
- un en-tête d'identité forgé envoyé directement par le client n'accorde
  jamais l'accès au compte.

Utilisez le navigateur automatisable fourni,
`/opt/pub-app/verifier_navigateur.py`, pour observer chacun de ces points
là où il se produit réellement, un vrai moteur de navigateur, pas
seulement des en-têtes de réponse.
