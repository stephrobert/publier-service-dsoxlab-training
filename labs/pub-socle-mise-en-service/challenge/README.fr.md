# La mission

## La situation

`service.mes.test` vient de vous être confié, en service sur `edge.lab` :
une seule route métier derrière du TLS, servie par deux origines, une
active et une candidate pour une future bascule. Le seul contrôle déjà fait
dessus, c'est qu'elle démarre.

Personne n'a encore exécuté de vraie matrice de recette depuis le client,
DNS compris. Personne n'a non plus essayé de restaurer sa configuration et
son état depuis la sauvegarde posée juste à côté ; une sauvegarde dont
personne n'a jamais restauré est une croyance, pas un fait. Et personne n'a
jamais fait revenir une bascule défaillante en arrière dessus, cache
compris.

## Mission

Réceptionnez vraiment cette publication, depuis `poste.lab`, le client
indépendant. Prouvez ensuite, sur `edge.lab`, que vous savez la perdre et la
récupérer, et défaire une bascule défaillante sans attendre l'expiration de
son cache. Terminez par un compte rendu honnête de ce que cette recette doit
encore à une vraie mise en service exposée sur Internet.

## Ce qui est demandé

Travaillez depuis `poste.lab` pour tout ce qui concerne le client, et depuis
`edge.lab` pour tout ce qui concerne l'opérateur. `/home/student/ca.pem` sur
`poste.lab` est l'autorité de test : n'utilisez jamais `curl -k` /
`--insecure`.

1. Exécutez la matrice de recette depuis `poste.lab` contre
   `https://service.mes.test/` : le DNS (`dig`, le vrai résolveur, pas un
   simple `--resolve` pour ce contrôle précis), le TLS et la route métier
   `/catalogue` (`--cacert ca.pem`), et la route interne `/interne/compte`,
   qui doit être refusée (403).

   L'un de ces contrôles échoue actuellement : `/etc/pub-mes/route.yaml`
   sur `edge.lab` porte un champ qui expose encore la route interne.
   Corrigez-le ; le routeur relit ce fichier à chaque requête.

   Écrivez ensuite `/home/student/recette.yaml` :

   ```yaml
   dns_ok: true
   tls_ok: true
   http_ok: true
   refus_ok: true
   ```

2. Écrivez `/home/student/restaurer.sh`, un script exécuté sur `edge.lab`
   qui restaure `/etc/pub-mes/route.yaml` et `/var/lib/pub-mes/stock.json`
   depuis `/var/backups/pub-mes/` et fait répondre au routeur la vraie
   valeur métier. Les tests suppriment réellement les deux fichiers actifs
   avant d'exécuter votre script : une sauvegarde dont personne n'a jamais
   restauré est une croyance, pas une preuve.

3. Écrivez `/home/student/revenir-origine.sh`, un script exécuté sur
   `edge.lab` qui fait revenir `origine_active` à `a` dans
   `/etc/pub-mes/route.yaml` et fait prendre en compte ce retour
   immédiatement par le routeur. Modifier seul le fichier ne suffit pas :
   `origine_active` est mis en cache pendant `ttl_cache_s` secondes. Lisez
   le comportement du routeur (`/opt/pub-mes/router.py` est sur `edge.lab`)
   pour trouver ce qui force une relecture immédiate.

4. Écrivez `/home/student/limites.yaml`, un compte rendu court et honnête
   nommant ce qu'une vraie mise en service exposée sur Internet exigerait
   encore au-delà de ce lab : un résolveur public, un client externe, une
   autorité de certification publique.
