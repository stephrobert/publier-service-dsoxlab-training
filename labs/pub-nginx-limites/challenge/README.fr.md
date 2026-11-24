# Scénario

Une API est publiée derrière Nginx, avec des limites déjà posées, et
posées de travers : une seule requête par minute, une zone unique partagée
par toutes les routes, et `set_real_ip_from 0.0.0.0/0`, qui fait croire à
Nginx le `X-Forwarded-For` de n'importe quel appelant.

La politique à appliquer est dans `/opt/pub-nginx-limites/politique.txt`.

## Mission

Appliquez la politique : le débit et la rafale annoncés par route, une
limite de corps, un refus en **429**, et un regroupement qui ne se laisse
pas forger.

## Le piège central : ce qui sert de clé

Regrouper par adresse IP est le réflexe, et il est faux ici. Les
utilisateurs sont **derrière un NAT** : ils partagent une adresse, donc
l'abus d'un seul les refuse tous.

Mais regrouper par un en-tête que l'appelant choisit lui-même est **pire** :
il lui suffit d'en changer à chaque requête pour n'être jamais compté.

La politique tranche : la clé d'API distingue les clients, et le
`X-Forwarded-For` n'est cru que du proxy amont déclaré, `127.0.0.1`. La
validation mesure les **deux côtés** de cet arbitrage : une adresse forgée
n'échappe pas à la limite, et une autre clé n'hérite pas de la pénalité.

## Ce qui est vérifié

- quinze requêtes d'affilée sur `/public` passent, puisque la politique
  admet une rafale de vingt. Une limite qui refuse le trafic normal est une
  panne qu'on s'inflige ;
- un abus reçoit un **429**, et non le 503 que Nginx rend par défaut. Un 503
  se lit comme une panne et invite à réessayer plus fort ; 429 est la seule
  réponse qui demande de ralentir ;
- **critique** : changer le `X-Forwarded-For` à chaque requête ne permet pas
  d'échapper à la limite, et une autre clé d'API n'est pas pénalisée pour
  autant ;
- marteler `/admin` ne ferme pas `/public`.

## Indices

- `limit_req_zone` déclare une zone et sa clé, `limit_req` l'applique.
  Plusieurs zones peuvent coexister, et c'est ce qui sépare les routes.
- `limit_req_status 429;` change le code de refus.
- `set_real_ip_from` liste les adresses dont le `X-Forwarded-For` est cru.
  Tout le reste du monde ne l'est pas.
- `client_max_body_size` borne le corps, et se déclare par `server` ou par
  `location`.
