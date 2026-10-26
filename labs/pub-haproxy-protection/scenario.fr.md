# Scénario

HAProxy publie déjà l'application sur `app.lab.test`, et il ne la protège
en rien : aucun en-tête de sécurité, `/admin` servi à qui le demande,
aucune limite de débit, et les méthodes d'écriture transmises jusqu'au
backend alors que l'application ne s'en sert pas.

## Mission

Ajoutez les en-têtes de sécurité, exigez les identifiants
`labadmin` / `Lab-Admin-Only` sur `/admin`, refusez en **429** un débit
supérieur à **20 requêtes par tranche de 10 secondes et par adresse
source**, et refusez `DELETE` et `PUT`. Tout cela sans casser les requêtes
normales de l'application.

## Ce qui est vérifié, et pourquoi dans les deux sens

Un refus ne se prouve qu'en montrant ce qui passe **encore**. Une
configuration qui rejetterait tout satisferait « `/admin` répond 401 », « le
débit excessif est refusé » et « `DELETE` est refusée » d'un seul coup, en
ayant simplement supprimé le service. Chaque contrôle porte donc son
contre-exemple :

- les quatre en-têtes sont présents **sur une réponse venue du backend**,
  et non sur une page d'erreur de HAProxy ;
- `/admin` répond **401** à l'anonyme **et** sert le backend avec les
  identifiants fournis ;
- une rafale de 40 requêtes rencontre **des 429 et des 200** : des 429
  seuls diraient une porte fermée, des 200 seuls une absence de limite. Et
  le service redevient disponible une fois la fenêtre écoulée, parce
  qu'une limite de débit **relâche**, au lieu de bannir ;
- `DELETE` et `PUT` sont refusées **et** `GET` atteint toujours le backend.

## Indices

- Une limite de débit par source se construit avec une `stick-table` de
  type `ip` portant un `http_req_rate`, et un `http-request deny deny_status
  429` au-delà du seuil.
- L'authentification se déclare dans un `userlist`, et s'exige avec
  `http-request auth` quand `http_auth` n'est pas satisfait.
- `http-response set-header` pose un en-tête sur la réponse ; le faire dans
  le `frontend` le pose pour tout ce qu'il sert.
- `docker compose restart` suffit à recharger la configuration, et
  `haproxy -c -f` la valide avant de la poser.
