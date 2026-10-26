# Scénario

Une configuration Nginx publie une application et une page
d'administration. Elle fonctionne, et elle se recouvre : un préfixe capte ce
qu'une expression régulière devait traiter, une redirection boucle, et
surtout **aucun server n'est déclaré par défaut**, si bien que tout nom
d'hôte inconnu atterrit sur le premier bloc du fichier, celui de
l'administration.

La matrice de sélection attendue est dans
`/opt/pub-nginx-routage/matrice.txt`.

## Mission

Réparez la sélection pour que chaque URL atteigne son gestionnaire, fermez
la porte au nom d'hôte inconnu, corrigez la redirection, et **écrivez votre
lecture de la règle de sélection** dans `/home/student/selection.yaml`.

## Pourquoi on vous demande une prédiction, et non une explication

Une machine ne sait pas juger une explication. La noter à la longueur et au
vocabulaire laisserait passer un texte incohérent, et ce catalogue en a fait
l'expérience ailleurs.

On vous demande donc de **prédire** où chaque URL de la matrice atterrit, et
la validation compare votre prédiction à ce que le serveur fait réellement.
Prédire juste sur une configuration fausse ne passe pas ; configurer juste
sans savoir le prédire non plus. C'est la même exigence, rendue mesurable.

## Ce qui est vérifié

- chaque URL de la matrice atteint le gestionnaire prévu. Le backend renvoie
  le nom du gestionnaire qui l'a appelé : on mesure ce qui est **choisi**,
  pas ce qui est écrit ;
- **critique** : un nom inconnu ne sert ni l'application ni l'administration,
  et reçoit un refus ;
- `/ancien` redirige vers `/nouveau` en conservant l'autorité, et sans
  boucler. Le test compte les sauts ;
- vos prédictions correspondent au comportement réel.

## Indices

- Nginx préfère une expression régulière à un préfixe simple, **sauf** si ce
  préfixe porte `^~`. Et une correspondance exacte `=` l'emporte sur tout.
- Un server par défaut se déclare avec `default_server` sur son `listen`.
  Celui qui ne sert rien est souvent le meilleur.
- Une redirection qui vise le préfixe dont elle part boucle. Le test suit
  jusqu'à cinq sauts puis abandonne.
