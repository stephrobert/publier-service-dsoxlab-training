# Scénario

Une application monopage, ses ressources, un fichier privé et une API sont
publiés par une configuration qui sert tout cela **sans distinction** :
aucun type MIME correct, un fallback qui avale toutes les erreurs, les
fichiers privés accessibles, et des permissions à `0777`.

Ce que la publication doit présenter est écrit dans
`/opt/pub-nginx-statique/attendu.txt`.

## Mission

Publiez les ressources prévues avec leur type, conservez les vraies
erreurs, refusez ce qui est privé, et resserrez les droits sans cesser de
servir.

## Le défaut le plus coûteux est celui qui ne se voit pas

Un `try_files $uri $uri/ /index.html` posé sur la racine transforme
**toute** erreur en succès. Une ressource absente rend 200 avec du HTML, et
un appel d'API inconnu aussi. La page s'affiche, tout a l'air de marcher, et
le défaut se diagnostique trois semaines plus tard, quand quelqu'un remarque
qu'un `fetch` reçoit du HTML au lieu de son JSON.

Le fallback reste pourtant **légitime** pour les routes de l'application :
`/accueil` doit bien rendre `index.html`. La validation exige donc les deux,
et c'est ce qui distingue une publication correcte d'une publication qui
marche.

## Ce qui est vérifié

- les ressources prévues ont le bon corps **et** le bon type MIME. Un
  JavaScript servi en `application/octet-stream` est téléchargé au lieu
  d'être exécuté ;
- le fallback sert les routes de l'application, et **seulement** elles :
  `/assets/absent.js` reste un 404, et l'API répond pour elle-même ;
- **critique** : le fichier privé, les dotfiles et les traversées de chemin
  sont refusés. Le test cherche le **secret dans le corps**, et non un code
  de statut : un 200 qui rend `index.html` sur `/.env` n'est pas une fuite,
  un 200 qui rend la clé en est une ;
- **critique** : plus aucun fichier n'est lisible par tout le monde, et les
  ressources sont toujours servies. Retirer tous les droits protégerait
  parfaitement et ne servirait plus rien.

## Indices

- `include mime.types;` charge la table des types de la distribution. Sans
  elle, `default_type` s'applique à tout.
- Un `try_files` limité à un `location` ne s'applique qu'à lui.
- Les workers tournent sous `www-data` : la lecture se donne par la
  propriété ou le groupe, jamais en ouvrant à tous.
