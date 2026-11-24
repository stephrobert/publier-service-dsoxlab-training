# Scénario

Nginx publie l'application sur `app.lab.test`, et n'en dit rien. Le journal
d'accès est au format `combined` par défaut : il ne porte ni le temps de
réponse, ni celui de l'amont. En le lisant, on ne peut donc pas savoir si
une lenteur vient de Nginx ou de l'application. Et aucun point d'état
n'est exposé.

## Mission

Exposez `stub_status` sur `127.0.0.1:8081/nginx_status`, **et sur la boucle
locale seulement**. Remplacez le journal d'accès de l'application par un
format **JSON, un objet par ligne**, portant au moins `status`,
`request_time` et `upstream_response_time`.

## Observer n'est pas écrire des champs

Un journal où `request_time` vaudrait toujours `0.000` serait structuré,
parsable, et parfaitement inutile. La validation confronte donc chaque
valeur journalisée à un fait qu'elle provoque :

- le point d'état répond en local **et** est refusé depuis l'adresse du
  réseau du lab. Exposé à tous, il donne à n'importe qui le nombre de
  connexions en cours du service ;
- chaque ligne est **parsée** comme du JSON, et non reconnue à la présence
  d'une accolade : un journal à moitié converti est exactement l'état où un
  collecteur rejette une ligne sur deux sans que personne le voie ;
- `/lent` met **deux secondes**, parce que le backend y dort deux secondes.
  Le `request_time` journalisé doit le dire ;
- `/casse` répond **503** et `/health` répond **200** : le journal doit
  distinguer les deux. Un journal qui écrirait 503 partout satisferait la
  première moitié du contrôle et serait faux.

## Indices

- `stub_status` se déclare dans un `location`, lui-même dans un `server`
  dont le `listen` porte l'adresse `127.0.0.1`.
- `log_format` accepte un littéral JSON ; pensez à `escape=json`, sans quoi
  une URL contenant un guillemet casse la ligne.
- `$request_time` est la durée vue par Nginx, `$upstream_response_time`
  celle de l'application. C'est leur écart qui désigne le coupable.
- `docker compose restart` recharge la configuration, et `nginx -t` la
  valide avant.
