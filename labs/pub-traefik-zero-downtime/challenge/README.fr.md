# La tâche

Éditez `/opt/pub-zds/dynamic/routes.yaml` (surveillé par les deux points
d'entrée) : remplacez le service `app` câblé en dur (un seul serveur,
`v1` uniquement) par un service `loadBalancer` qui liste **les deux**
backends comme serveurs (`http://pub-zds-app-v1:8080` et
`http://pub-zds-app-v2:8080`, chacun avec un `weight` explicite), et
ajoutez un `loadBalancer.healthCheck` (chemin `/health`, un intervalle
court comme `2s`) qui s'applique à tous les serveurs de ce service. Le
type de service `weighted` de Traefik (qui combine deux sous-services
nommés) ne redistribue **pas** le trafic d'un sous-service malsain : les
sondes de santé ne retirent de la rotation que des *serveurs* au sein
d'un même `loadBalancer`, donc les deux versions doivent être deux
serveurs d'un même service pondéré, pas deux sous-services pondérés
séparés. Ajustez les poids pour déplacer le trafic de `v1` vers `v2`,
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
