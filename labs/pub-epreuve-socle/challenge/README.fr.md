# La mission

## La situation

`epreuve.test` répond sur `edge.lab`, en TLS, derrière un routeur qui
relaie vers un backend protégé portant une valeur métier et sa sauvegarde.
Tout cela est en place avant votre arrivée : on vous confie un service en
fonctionnement, pas une machine vierge. Peu après sa mise en service, un
incident a été introduit, sans vous dire quelle couche il touche.

## Mission

D'abord, comprenez et documentez ce que vous observez : produisez le
dossier d'architecture du service tel qu'il est réellement. Prouvez
ensuite qu'il fonctionne, depuis `poste.lab`, le client indépendant, avec
des données que vous n'avez pas choisies à l'avance et sans jamais
relâcher la vérification TLS. En cours de route, vous constaterez que le
service ne se comporte pas comme le dossier le prétend : diagnostiquez la
cause réelle à partir de ce que vous observez, réparez par une
modification minimale, et expliquez votre raisonnement. Enfin, exercez la
sauvegarde déjà présente sur `edge.lab` : restaurez-la et montrez que le
résultat est digne de confiance, pas seulement qu'il fonctionne.

## Ce que la machine note, et ce qu'un relecteur lit

Cette distinction n'est pas une formalité : une machine ne sait pas juger
un document, et prétendre le contraire reviendrait à valider un texte
incohérent au motif qu'il est assez long et qu'il emploie les bons mots.

**Noté par la validation**, parce que cela se compare à l'état réel de la
machine :

- le dossier **existe** et **nomme le service** qu'il documente ;
- le service répond depuis `poste.lab` avec une donnée choisie au moment
  de l'essai, sous vérification TLS stricte, et `/admin` reste refusé ;
- le champ **`couche`** de `incident.yaml` désigne la couche réellement
  cassée, et le champ **`composant`** nomme le composant fautif sans citer
  de couche sans rapport ;
- le champ **`explication`** est **présent** ;
- la restauration s'exécute et le résultat est vérifiable.

**Lu par un relecteur, et non noté ici** : la pertinence du dossier, sa
couverture des noms, des flux, des identités et des responsabilités, et la
qualité du raisonnement écrit dans `explication`. Les hypothèses que vous
avez écartées ont leur place dans ce champ : les y écrire ne vous pénalise
pas, c'est au contraire ce qu'on attend d'un diagnostic.

## Ce qui est demandé

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
