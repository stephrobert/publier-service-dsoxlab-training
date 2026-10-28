# Scénario

Trois transports longs sont publiés derrière Nginx, et tous les trois sont
traités comme des pages : le WebSocket n'établit jamais sa poignée de main,
les événements SSE sont retenus en tampon, gRPC passe par un proxy HTTP
ordinaire, et un délai de lecture de dix secondes coupe tout flux en pleine
conversation.

Le banc est décrit dans `/opt/pub-nginx-flux-longs/transports.txt`.

## Mission

Publiez les trois transports sans retarder les événements ni bloquer les
échanges légitimes, et faites survivre une conversation qui se tait.

## Ce que chaque transport exige, et qui diffère

Le **WebSocket** a besoin que la poignée de main soit transmise : les
en-têtes `Upgrade` et `Connection`, sur une connexion en HTTP/1.1 vers le
backend. Cette version est le défaut depuis nginx 1.29.7, donc seuls les
en-têtes manquent ici.

Le **SSE** a besoin que rien ne soit mis en tampon. C'est le piège le plus
sournois du lab, parce qu'un test naïf le rate : les six événements
**finissent** par arriver. Ce qui distingue un flux d'un lot, c'est le
**rythme**, donc la validation mesure le délai du premier événement.

Le **gRPC** a besoin d'HTTP/2 et de `grpc_pass`, sur un port dédié en clair.
Et il a besoin qu'un refus applicatif reste un refus applicatif : un
`INVALID_ARGUMENT` qui parvient au client en `UNAVAILABLE` le fera
réessayer indéfiniment une requête qui n'aboutira jamais.

Les trois, enfin, ont besoin de **temps**. Le réglage de départ coupe toute
route dont le backend n'a rien dit depuis dix secondes, ce qui est
exactement ce que fait un flux long : il se tait. `proxy_read_timeout`
compte le temps écoulé **entre deux lectures**, et non la durée du flux.

## Ce qui est vérifié

- la poignée de main WebSocket aboutit **et** une trame envoyée revient. La
  seconde moitié compte : une connexion établie qui ne transporte rien est
  la version la plus difficile à diagnostiquer de ce défaut ;
- le **premier** événement SSE arrive en moins de quatre secondes, alors que
  le backend en émet six à une seconde d'intervalle ;
- un appel gRPC aboutit, et la charge `erreur` revient comme refus
  applicatif, pas comme panne de transport ;
- une conversation WebSocket qui se tait quinze secondes **survit**, et
  reprend ensuite. C'est le silence qui coupe, pas la durée : un flux
  bavard ne déclenche jamais ce délai, et le défaut ne se montre qu'en
  production, sur la conversation qui n'avait rien à dire pendant une
  minute.

## Indices

- `proxy_set_header Upgrade $http_upgrade;` et `proxy_set_header Connection`.
  La valeur `"upgrade"` en dur convient sur une route dédiée comme `/ws` ;
  dès que la route porte aussi du trafic ordinaire, elle se calcule par un
  `map` sur `$http_upgrade`, sans quoi toute requête qui passe par ce
  `location` demande une bascule de protocole. `proxy_http_version` n'est pas
  ce qui manque : 1.1 est le défaut depuis nginx 1.29.7. L'écrire ne nuit
  pas, et porte même la configuration sur un nginx plus ancien, mais cela ne
  répare rien ici.
- `proxy_buffering off;` dans le `location` du flux, et non globalement :
  le tampon reste utile partout ailleurs.
- `grpc_pass grpc://...` sur un `server` dont le `listen` porte `http2`.
- Les délais se règlent par route : un flux long n'a pas les mêmes besoins
  qu'une page.
