# La mission

Travaillez depuis `poste.lab` pour tout ce qui concerne le client, et
depuis `edge.lab` pour tout ce qui concerne l'opérateur.
`/home/student/ca.pem` sur `poste.lab` est l'autorité de test : n'utilisez
jamais `curl -k` / `--insecure`.

1. **Dossier (`besoin`).** Observez le service tel qu'il tourne
   réellement : `dig epreuve.test A`, `curl --cacert ca.pem --resolve
   epreuve.test:443:<ip-edge> https://epreuve.test/`, `systemctl status
   pub-eps-router pub-eps-backend` sur `edge.lab`. Écrivez
   `/home/student/dossier.md` sur `edge.lab` : les noms en jeu, le flux du
   client au backend (ce qui termine TLS, ce qui n'est joignable que de
   là), les identités (qui a signé le certificat, à qui il est délivré), et
   les responsabilités (ce que fait le routeur, ce que le backend impose
   lui-même, comme `/admin`). Ce dossier est jugé sur la cohérence de ce
   que vous avez observé, pas sur sa longueur.

2. **Preuve (`preuve`, critique).** Depuis `poste.lab`, prouvez que le
   service fonctionne réellement pour un client indépendant : demandez `/`
   avec un nonce que vous choisissez au moment de la requête
   (`?nonce=...`) et vérifiez qu'il revient dans la réponse, avec la vraie
   valeur métier, récupérée sous vérification TLS stricte (jamais `-k`).
   Confirmez aussi que `/admin` est refusée (`403`).

3. **Incident (`incident`, critique).** À un moment, vous constaterez que
   le service ne répond pas comme le dossier le prétend : un incident, non
   annoncé, a été introduit sur l'une de cinq couches (DNS, transport,
   TLS, la route, ou le backend). Observez, formulez une hypothèse, et une
   fois la couche et le composant réels connus, écrivez
   `/home/student/incident.yaml` sur `edge.lab` :

   ```yaml
   couche: route    # un parmi : dns, transport, tls, route, backend
   composant: "..."
   explication: "..."
   ```

   Nommez uniquement la cause réelle, appuyée sur ce que vous avez
   réellement observé. Citer toutes les couches « au cas où » ne compte
   pas comme un diagnostic. Réparez par la modification la plus minime qui
   fonctionne, sous `/etc/pub-eps/` (`route.yaml`), les unités systemd
   `pub-eps-router.service` et `pub-eps-backend.service`, ou la zone
   unbound dans `/etc/unbound/unbound.conf.d/pub-eps.conf`. Prouvez que le
   service répond à nouveau, en le retestant plusieurs fois.

4. **Reprise (`reprise`, critique).** Une sauvegarde est déjà présente
   dans `/var/backups/pub-eps/` (`route.yaml.bak`, `donnees.json.bak`) :
   prise avant l'incident, mais personne n'a encore prouvé qu'elle
   restaure réellement quoi que ce soit. Écrivez
   `/home/student/restaurer.sh` sur `edge.lab` : un script qui restaure
   `/etc/pub-eps/route.yaml` et `/var/lib/pub-eps/donnees.json` depuis ce
   répertoire de sauvegarde, de sorte que le routeur serve la vraie
   configuration et le backend la vraie valeur métier, sans toucher au
   certificat ni à l'autorité qui l'a signé. Il sera exécuté avec `sudo
   bash /home/student/restaurer.sh` après que les deux fichiers en
   production ont été supprimés : assurez-vous qu'il ne dépend de rien
   d'autre qui serait encore en place.
