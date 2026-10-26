# Scénario

Une pile de publication était saine. Elle fronte une page statique, deux
backends, et une route de contrôle. Une panne **réelle** y a été injectée,
tirée au hasard parmi cinq familles :

- **sélection** : une route part vers le mauvais backend ;
- **permission** : un fichier ou un répertoire n'est plus lisible par qui le
  sert ;
- **résolution** : le nom du backend ne se résout plus ;
- **confiance TLS** : le magasin de confiance du proxy ne reconnaît plus le
  certificat du backend ;
- **délai** : une borne d'attente est devenue plus courte que le service.

Vous ne savez pas laquelle. Et il y a du **bruit** autour : un bloc `server`
pour un nom de domaine abandonné, un fichier de `conf.d/` qui ne contient
que des commentaires, un `gzip on` en double, un `proxy_pass` commenté qui
porte un mauvais port. Chacun a l'air suspect. Aucun n'explique la panne.

## Mission

Trouvez la panne, corrigez-la, et vérifiez **toute** la recette, qui est
dans `/opt/pub-nginx-depannage/recette.txt`.

Écrivez par ailleurs `/opt/pub-nginx-depannage/diagnostic.md` : le composant
en cause, la cause, et les observations qui vous y ont menés.

## Ce que la validation juge, et ce qu'un relecteur lit

La validation automatique ne connaît pas la variante active : elle ne peut
donc pas vérifier « la bonne correction ». Elle mesure l'**état final de la
recette**, le même pour les cinq variantes. C'est aussi la bonne façon de
faire : après une panne, on ne rejoue pas le test de ce qu'on vient de
réparer, on rejoue la recette entière. C'est comme cela qu'on attrape la
correction qui répare une chose en cassant une autre.

Du dossier de diagnostic, elle juge la **présence** et le fait qu'il nomme
un composant. Elle ne juge pas le raisonnement, et ne le prétend pas : c'est
un relecteur qui le lit. Un contrôle qui noterait la qualité d'une
explication noterait en réalité la présence de mots-clés, et apprendrait à
en semer.

## Les deux desserrages que la recette interdit

Deux variantes se « réparent » en desserrant quelque chose, et les deux
marcheraient :

- `proxy_ssl_verify off` ferme la variante TLS en acceptant n'importe quel
  certificat de backend ;
- faire tourner les workers en `root` ferme la variante de permission sans
  toucher aux permissions.

La pile porte donc une **sonde de confiance**, `/api-secondaire/`, qui pointe
vers un backend dont le certificat vient d'une autre autorité et dont le SAN
ne correspond pas. Elle doit répondre **502**, et c'est tout ce qu'elle doit
faire. Si elle répond 200, la vérification TLS a été desserrée. Les deux
contrôles sont **critiques**.

## Ce qui est vérifié

- la racine statique, `/app/` et `/api/` rendent **leur** marqueur. Les trois
  sont différents : une route qui part vers le backend voisin répond 200 sans
  broncher, et seul le marqueur le dit ;
- `/api/lent` passe, et une requête qui n'avance plus est coupée par le
  proxy en moins de quinze secondes, avec un **504**. Un `000` veut dire que
  c'est curl qui a abandonné, pas le proxy ;
- **critique** : les workers ne tournent pas sous `root`, les ports des
  backends ne sont pas joignables depuis le réseau, et la racine statique
  n'est pas ouverte en écriture à tout le monde ;
- **critique** : la sonde de confiance répond 502, et `/api/` répond 200.
  Une vérification qui refuse aussi le bon backend n'a rien vérifié, elle a
  tout fermé.

## Où regarder

- `systemctl status nginx` et `nginx -t` disent beaucoup quand le service ne
  démarre pas, et ils le disent en nommant le fichier et la ligne.
- `nginx -T` rend la configuration **effective**, tous les `include`
  résolus : c'est ce que Nginx lit, par opposition à ce qu'on croit lui avoir
  écrit.
- `/var/log/nginx/error.log` distingue un 403 de permission d'un 502 de
  confiance, et nomme le fichier ou le certificat en cause.
- `curl -v` depuis la machine elle-même sépare ce qui est cassé dans le proxy
  de ce qui est cassé dans le backend.
- Les ordres de sélection d'une `location` ne sont pas ceux de l'écriture :
  `=`, puis `^~`, puis les expressions régulières dans l'ordre du fichier,
  puis le plus long préfixe.
