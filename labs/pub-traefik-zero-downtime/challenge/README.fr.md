# La tâche

## La situation

`zds.lab.test` est servi par deux points d'entrée Traefik jumeaux sur
`edge.lab` (ports lisibles dans `/opt/pub-zds/ports.env`), tous deux
surveillant exactement la même configuration dynamique et servant
exactement le même certificat. Le trafic de production est câblé en dur
sur le backend `v1` ; une candidate `v2` tourne déjà, saine, et joignable
sur le réseau Docker, mais rien dans la configuration actuelle ne permet
d'y déplacer le trafic progressivement, et rien ne retire un backend de la
rotation s'il cesse de répondre correctement : le service réparti ne porte
aucune sonde de santé. Un outil de rotation de certificat,
`/opt/pub-zds/outils/tourner-certificat.sh`, est partagé par les deux
points d'entrée ; il a été écrit en supposant qu'il ne tourne jamais qu'une
fois à la fois, ce qui n'est pas une hypothèse sûre pour un outil destiné à
servir deux points d'entrée indépendants.

## Mission

Lisez `/opt/pub-zds/README`, puis :

- Construisez un vrai chemin progressif de `v1` vers `v2` : **deux
  serveurs pondérés d'un même service Traefik réparti**, et non un service
  de type `weighted` combinant deux sous-services séparés. Montrez le
  trafic circuler par les deux versions pendant la transition, avec une
  part d'erreurs bornée.
- Ajoutez une sonde de santé au répartiteur du service pour que, lorsque
  `v2` est marquée malsaine (son marqueur `/app/healthy` retiré, simulant
  une vraie panne), elle soit réellement retirée de la rotation et que le
  trafic revienne à `v1` sans qu'un humain n'édite quoi que ce soit à la
  main.
- Depuis `poste.lab`, observez ce qui se passe quand on arrête le
  processus d'un point d'entrée (l'autre doit continuer à servir), et ce
  qui se passe quand l'hôte unique qui porte les deux points d'entrée
  devient injoignable (les deux s'arrêtent nécessairement, puisqu'ils
  partagent un seul domaine de panne). Écrivez votre conclusion, pour
  chacune des deux pannes, sous la forme `survit` ou `ne_survit_pas`, dans
  `/home/student/domaine-de-panne.yaml` :

  ```yaml
  perte_processus: survit
  perte_hote: ne_survit_pas
  ```

  Ne devinez pas : déclenchez chaque panne pour de vrai et observez le
  point de vue du client avant d'écrire le fichier. Prétendre à une
  résilience que ce lab à une seule VM n'a pas est pire que d'en admettre
  la limite.
- Corrigez `/opt/pub-zds/outils/tourner-certificat.sh` pour qu'une
  exécution double, en même temps, depuis les deux points d'entrée, ne
  laisse jamais une paire certificat/clé dépareillée ou illisible dans le
  stockage partagé ; les deux points d'entrée doivent continuer à servir
  du TLS valide ensuite.

## Ce qui est demandé

Éditez `/opt/pub-zds/dynamic/routes.yaml` (surveillé par les deux points
d'entrée) : remplacez le service `app` câblé en dur (un seul serveur,
`v1` uniquement) par un service `loadBalancer` qui liste **les deux**
backends comme serveurs (`http://pub-zds-app-v1:8080` et
`http://pub-zds-app-v2:8080`, chacun avec un `weight` explicite), et
ajoutez un `loadBalancer.healthCheck` (chemin `/health`, un intervalle
court comme `2s`) qui s'applique à tous les serveurs de ce service. Le
type de service `weighted` de Traefik (qui combine deux sous-services
nommés) **peut** retirer un sous-service malsain, mais seulement s'il
porte lui-même un `healthCheck`, et à trois conditions : il faut
l'activer, tous ses descendants doivent en avoir un sinon la création du
service échoue, et il n'est défini qu'avec le fournisseur fichier. Sans
ce `healthCheck`, rien n'est câblé et l'enfant malsain reste dans la
rotation.

Ce lab demande donc la forme la plus simple, qui ne dépend d'aucune de
ces conditions : **deux serveurs d'un même service pondéré**, dont les
sondes retirent individuellement un serveur de la rotation. Ajustez les poids pour déplacer le trafic de `v1` vers `v2`,
observez le mélange réel et le taux d'erreur avec de vraies requêtes
HTTP, puis retirez `/app/healthy` de `pub-zds-app-v2` (`docker exec
pub-zds-app-v2 rm /app/healthy`) et confirmez que le trafic revient seul
vers `v1` ; restaurez ensuite la santé de `v2` avec `docker exec
pub-zds-app-v2 touch /app/healthy`.

Depuis `poste.lab`, interrogez `https://zds.lab.test:<port>/` (ports dans
`/opt/pub-zds/ports.env`) sur chaque point d'entrée, arrêtez
`pub-zds-entry-a` et confirmez que `pub-zds-entry-b` répond toujours,
puis redémarrez `pub-zds-entry-a`. Pour observer la panne au niveau de
l'hôte, bloquez les deux ports en même temps sur `edge.lab`, avant que le
NAT de Docker ne les réécrive (par exemple avec `iptables -t raw -I
PREROUTING -p tcp --dport <port> -j DROP` pour chacun, car une simple
règle `-I INPUT` ne voit pas le trafic que Docker a déjà redirigé vers un
conteneur) et confirmez que les deux points d'entrée deviennent
injoignables depuis `poste.lab` ; retirez ensuite la règle. Écrivez votre
conclusion dans `/home/student/domaine-de-panne.yaml` avec les clés
`perte_processus` et `perte_hote`, chacune valant `survit` ou
`ne_survit_pas`.

Corrigez `/opt/pub-zds/outils/tourner-certificat.sh` pour qu'une
invocation concurrente et répétée depuis deux appelants ne laisse jamais
`/opt/pub-zds/tls/tls.crt` et `tls.key` dépareillés ou tronqués : écrivez
dans un chemin temporaire puis renommez les deux fichiers en place de
façon atomique (ou sérialisez avec un verrou), pour que tout observateur
voie toujours soit l'ancienne paire complète, soit la nouvelle paire
complète, jamais un mélange. Redémarrez les deux conteneurs Traefik après
une rotation si besoin (le fournisseur de fichiers recharge les routes à
chaque changement, mais le certificat par défaut référencé par `tls:` est
lu quand une connexion qui en a besoin est négociée, ce qui suffit
normalement ; redémarrer reste un filet de sécurité si un test voit
encore une poignée de main périmée).
