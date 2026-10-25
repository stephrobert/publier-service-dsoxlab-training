# La mission

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
