# Scénario

Un catalogue est publié derrière Nginx, avec un cache déjà posé, et posé de
travers. Quatre défauts cohabitent, et le premier les explique presque tous :

- `proxy_ignore_headers Cache-Control Expires Set-Cookie` : le contrat que
  l'origine annonce sur chacune de ses réponses est jeté ;
- `proxy_cache_key "$uri"` : la clé ne voit ni la langue demandée, ni la
  session, ni la chaîne de requête ;
- `proxy_cache_valid 200 10m` appliqué à tout, sans distinguer une page
  stable d'un état de stock qui bouge ;
- `add_header X-Cache-Status "HIT" always`, qui annonce HIT sur **toutes**
  les réponses, y compris celles qui sortent de l'origine.

Le contrat de contenu est dans `/opt/pub-nginx-cache/contrat-de-contenu.txt`.

## Mission

Appliquez ce contrat : les réponses publiques éligibles sont réellement
servies depuis le cache, les variantes de représentation ne se mélangent
pas, aucune réponse privée ne passe d'un compte à l'autre, et le contenu
volatil reste frais.

## Ce que la validation ne lit jamais : `X-Cache-Status`

Un cache se vérifie d'ordinaire en lisant cet en-tête. C'est une
**déclaration** de Nginx, pas une mesure, et c'est Nginx qu'on vérifie. Le
quatrième défaut est là pour le montrer : il affiche HIT sur un MISS, et
n'importe quel contrôle qui le croirait conclurait au vert sur un cache
inexistant.

La mesure se prend donc à l'origine, sur la boucle locale de la VM, où
Nginx n'a aucune prise : l'application compte ses **générations de corps**.
Un HIT devient alors un fait, une réponse rendue sans que l'origine ait
rien produit. Un `304` n'est pas compté comme une génération, pour qu'une
politique de revalidation passe la mesure au même titre qu'une durée courte.

## Ce qui est vérifié

- une deuxième demande sur la page d'accueil publique ne fait **rien**
  produire à l'origine ;
- une demande en anglais ne reçoit pas la rédaction française, et la
  variante française reste pour autant servie depuis le cache. Les deux
  côtés comptent : séparer les variantes en renonçant à les mettre en cache
  ne répond pas au contrat ;
- **critique** : le marqueur du compte alpha, tiré au hasard, n'atteint
  jamais le compte beta ni une demande anonyme, et la page publique reste
  pour autant en cache. Retirer le cache n'est pas le corriger ;
- sept secondes après un changement à l'origine, `/catalogue/stock` porte la
  nouvelle valeur, et deux demandes qui se suivent ne font pas produire deux
  corps.

Les chemins de la validation portent un jeton unique par mesure, que
l'origine ignore et qui désigne la même ressource : chaque mesure part ainsi
d'une entrée de cache froide, quelle que soit la clé que vous choisissez.

## Indices

- `proxy_cache_valid` ne s'applique que si le `Cache-Control` de l'origine
  n'est pas ignoré. Enlever une directive est parfois tout le correctif.
- Nginx honore `Vary` depuis la 1.7.7 : une origine qui annonce
  `Vary: Accept-Language` suffit à ranger les variantes séparément, sans
  toucher à la clé.
- `proxy_no_cache` et `proxy_cache_bypass` décident de ne pas **ranger** et
  de ne pas **servir** depuis le cache, et les deux se déclarent.
- `proxy_cache_revalidate on` fait revalider une entrée périmée avec son
  `ETag` plutôt que de la régénérer.
- `add_header X-Cache-Status $upstream_cache_status;` rend un en-tête qui
  dit la vérité. Ce n'est pas noté, mais c'est ce qui rend un cache
  observable.
