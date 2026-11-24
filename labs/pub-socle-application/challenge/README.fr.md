# La tâche

## La situation

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

## Ce qui est demandé

Sur `edge.lab`, modifiez `/etc/pub-app/politique.yaml` (relu à chaque
requête, aucun redémarrage nécessaire) pour que les quatre points
ci-dessous soient vrais. Rien d'autre n'est à écrire : les tests observent
directement l'application et le point d'entrée, avec le navigateur
automatisable déjà installé.

```yaml
entete_proto:
  transmettre: <true|false : le point d'entrée dit-il à l'application
    qu'il a réellement terminé le HTTPS, au lieu de laisser l'application
    supposer qu'elle ne l'est jamais ?>
cookie:
  domaine: <l'attribut Domain du cookie de session : une chaîne littérale
    qu'un navigateur acceptera réellement pour cet hôte, ou vide pour
    laisser le navigateur le déduire correctement>
cors:
  autoriser_toutes_origines: <true|false : la politique dit-elle oui à
    toute origine, au lieu de la vérifier contre la seule origine
    partenaire réellement approuvée ?>
  origine_autorisee: <laissée telle que fournie, ne la changez pas>
identite:
  faire_confiance_entete_client: <true|false : le point d'entrée
    reconduit-il l'en-tête d'identité déjà envoyé par le client, au lieu
    de le décider à partir du cookie de session qu'il a réellement
    validé ?>
```

Lisez `/home/student/README-app` pour les ports exacts de cette session.
Utilisez le navigateur automatisable fourni pour vérifier votre propre
travail avant de compter sur les tests :

```sh
sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
  python3 /opt/pub-app/verifier_navigateur.py parcours <port_entree>
sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
  python3 /opt/pub-app/verifier_navigateur.py cors <port_partenaire> <port_intrus>
sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
  python3 /opt/pub-app/verifier_navigateur.py identite <port_entree>
```

Les tests lancent eux-mêmes ces trois mêmes vérifications, depuis
`edge.lab`, et ne font jamais confiance à un seul en-tête de réponse quand
le point testé est précisément ce qu'un vrai navigateur impose.
