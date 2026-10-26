# Scénario

Un service est publié en TLS derrière Nginx, dans sa génération **1.4.2**.
Une seconde génération, **1.5.0**, est déjà sur le disque. Chacune a son
propre port et son **propre certificat**, et les deux certificats portent le
même nom de service : `service.lab.test`.

Le manifeste est dans `/opt/pub-nginx-mise-a-jour/manifeste.txt`, le plan
dans `/opt/pub-nginx-mise-a-jour/plan.txt`.

## Mission

Écrivez les deux exécutables que le plan demande :

- `livrer <version>`, qui rend la main quand cette génération est
  **réellement servie**, avec son certificat, et qui est idempotent ;
- `revenir`, sans argument, qui ramène la génération précédemment servie,
  avec **son** certificat.

Le langage vous appartient. Et tenez `journal.md` : vos mesures, et ce que
vous en concluez.

## La validation pilote, elle ne constate pas

C'est ce qui distingue ce lab des autres. Un test qui tourne une fois, à la
fin, ne voit qu'un état final : il ne peut rien dire d'une séquence, et
encore moins de la disponibilité pendant une bascule, qui ne se mesure pas
après.

La validation joue donc **vos** exécutables, dans l'ordre du plan, et mesure
entre chaque appel. Le livrable est le mécanisme de livraison, pas l'état du
service.

## Ce qu'elle mesure, et où

La **version servie**, depuis le client, et non ce que le disque contient ni
ce qu'un lien symbolique désigne. Les trois peuvent différer, et c'est le
défaut que ce lab enseigne : une génération basculée sur le disque sans que
le processus soit remplacé laisse l'ancien code en mémoire.

L'**empreinte du certificat publié**, lue dans la poignée de main. Rien dans
le nom du service ne dit quelle génération est publiée : seule l'empreinte le
dit. C'est pour cela qu'un retour arrière qui oublie le certificat n'a l'air
de rien.

## Ce qui est vérifié

- l'état de départ est bien la génération 1.4.2 avec son certificat, et les
  deux exécutables existent et sont exécutables ;
- après `livrer 1.5.0`, la version servie et l'empreinte publiée sont celles
  que le manifeste donne à 1.5.0 ;
- pendant la bascule, une sonde continue tourne : **au plus une** requête en
  échec sur la série. Les deux générations ont chacune leur port, donc elles
  peuvent tourner en même temps, et c'est ce qui rend le zéro-erreur
  atteignable ;
- un **flux long** ouvert avant la bascule continue de recevoir après. Une
  livraison ne coupe pas la génération précédente ; c'est la livraison
  suivante qui la retire ;
- `journal.md` existe et parle du flux long. La machine juge sa présence et
  son sujet, pas sa qualité : un contrôle qui noterait une explication
  noterait en réalité la présence de mots-clés ;
- **critique** : `revenir` ramène 1.4.2 **et** son certificat ;
- **critique** : après un redémarrage de la machine, la recette passe sans
  qu'on touche à rien.

## Indices

- `systemctl reload nginx` garde les connexions établies sur les anciens
  workers ; `restart` les coupe toutes. La différence ne se voit que sur un
  flux long.
- Une unité systemd modèle (`unite@instance.service`) donne une unité par
  génération sans rien éditer. `%i` y vaut l'instance.
- `enable` et `start` ne sont pas la même chose, et c'est le dernier test qui
  fait la différence.
- `revenir` a besoin d'une mémoire. `/run` et `/tmp` sont vidés au
  démarrage ; `/var/lib` ne l'est pas.
- `openssl s_client -connect ip:443 -servername nom` montre le certificat
  réellement publié, et `openssl x509 -noout -fingerprint -sha256` en donne
  l'empreinte.
