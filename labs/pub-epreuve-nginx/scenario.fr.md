# Scénario

On vous remet un Nginx vide et un cahier des charges. L'équipe produit a un
site statique et une API à mettre en ligne sous deux noms,
`www.epreuve.test` et `api.epreuve.test`. Une autorité ACME locale (Pebble) et
un client ACME (lego, en image de conteneur épinglée) sont disponibles, le
contenu du site et l'API sont déjà sur `edge.lab`, et rien d'autre n'existe :
ni configuration Nginx, ni certificat, ni sauvegarde, ni alerte.

Le banc est décrit dans `/opt/pub-epreuve-nginx/LISEZ-MOI.txt` et dans
`/home/student/README-epreuve` sur `edge.lab`. Vous travaillez depuis
`edge.lab` pour le côté opérateur et depuis `poste.lab`, le client
indépendant, pour prouver ce qu'un visiteur reçoit vraiment. N'utilisez
jamais `curl -k` : la validation stricte fait partie de ce qui est noté.

## Mission

Publier le service puis l'exploiter, en cinq temps.

1. **Publier.** Servez le site statique sur `www.epreuve.test` et l'API sur
   `api.epreuve.test`, en HTTPS avec une chaîne validée strictement, à partir
   du contenu là où il se trouve (ne le copiez pas). HTTP redirige vers HTTPS,
   un nom inconnu ne sert rien, et les certificats se renouvellent pour de
   bon.
2. **Fixer la politique.** `/admin` sur l'API demande les identifiants de
   `/opt/pub-epreuve-nginx/admin.htpasswd` (utilisateur et mot de passe dans
   `/home/student/README-epreuve`) ; les fichiers cachés du site ne
   sont jamais servis ; l'API refuse toute méthode autre que `GET` et `HEAD` ; le
   backend n'est jamais joignable depuis le réseau ; la réponse publique de
   l'API est mise en cache, et aucune réponse privée ne passe jamais d'une
   session à une autre.
3. **Exploiter.** Le flux long `/v1/flux` est livré au rythme du backend ; le
   journal d'accès est en JSON avec des durées qui mesurent ; une page d'état
   répond sur l'interface de bouclage seulement ; une alerte sonne quand le
   service est en panne et retombe quand il est revenu.
4. **Rendre compte de votre recette initiale, puis affronter l'incident.**
   Quand votre service passe votre propre recette, écrivez
   `/home/student/recette-initiale.md`. Cette écriture libère l'incident :
   quelques secondes plus tard, quelque chose change sur la machine, sans qu'on
   vous dise quelle couche est touchée. Diagnostiquez-le d'après ce que vous
   observez, réparez-le par le plus petit changement, et expliquez.
5. **Prouver votre plan de reprise.** Faites une sauvegarde, perdez la
   configuration et les certificats, restaurez depuis votre sauvegarde, puis
   redémarrez la machine et rejouez la recette complète sans rien toucher.

## Les points d'entrée que la validation appelle

La validation ne peut pas connaître le mécanisme que vous choisissez : elle
appelle des points d'entrée fixes et mesure le résultat. Tous s'exécutent en
root sur `edge.lab`.

| Point d'entrée | Ce que la validation attend |
|---|---|
| `/usr/local/bin/renouveler-certificats` | renouvelle les certificats des deux noms et met la nouvelle série en service par un reload, avec le même compte ACME |
| `/usr/local/bin/sauvegarder-service` | sauvegarde ce qui permet de remettre le service en route |
| `/usr/local/bin/restaurer-service` | le restaure, que Nginx tourne ou soit arrêté |
| `/usr/local/bin/sonde-alerte` | sort avec `0` quand le service est sain, avec un code non nul sinon, et revient à `0` dans les 90 secondes qui suivent le rétablissement |

Des emplacements fixes, parce qu'un contrôle doit les trouver sans deviner :

- le journal d'accès JSON est `/var/log/nginx/epreuve.json`, et chaque ligne
  porte au moins `status`, `request_time` et `upstream_response_time` ;
- la page d'état est `http://127.0.0.1:8081/nginx_status` ;
- le client ACME garde ses données sous `/opt/pub-epreuve-nginx/lego`, son
  compte dans `accounts/`, et son répertoire de défi HTTP-01 est
  `/opt/pub-epreuve-nginx/defi` ;
- le diagnostic est `/home/student/incident.yaml`, avec les trois champs
  `couche`, `composant` et `explication`.

## Ce que la machine note, et ce qu'un relecteur lit

**Noté par la validation**, parce qu'elle peut le comparer à l'état réel de la
machine :

- **publication** (critique) : le bon contenu par nom, une chaîne validée
  strictement sur les deux noms, HTTP qui redirige vers HTTPS, et un
  renouvellement qui sert une **nouvelle série** sans redémarrer Nginx ni
  changer le compte ACME, avec des clés privées qui ne sont pas lisibles par
  tous ;
- **politique** (critique) : la matrice de refus (administration sans
  identifiants ou avec un mauvais mot de passe, en-têtes d'identité forgés,
  fichiers cachés, méthodes inutilisées, accès direct au backend), et un cache
  qui ménage l'origine pour les réponses publiques pendant que deux sessions
  alternées ne voient jamais les données l'une de l'autre ;
- **exploitation** : le rythme du flux, un journal dont les durées
  correspondent à des faits que la validation provoque, la page d'état
  réservée à la boucle locale, et l'alerte dans les deux sens pendant une panne
  contrôlée du backend ;
- **incident** (critique) : le champ `couche` nomme la couche réellement en
  cause (`amont`, `tls`, `droits` ou `entetes`), le champ `composant` nomme le
  composant fautif **sans citer une autre variante**, le champ `explication`
  est présent, le service répond de nouveau plusieurs fois de suite, et la
  réparation n'a perdu aucune garantie : TLS strict, administration fermée,
  backend inaccessible, aucun droit élargi, code du backend intact ;
- **reprise** (critique) : la sauvegarde est restaurée après destruction de la
  configuration et des fichiers de certificat, le certificat revient
  **identique** avec sa clé fermée, et après un redémarrage la recette complète
  repasse sans aucune intervention.

**Lu par un relecteur, et non noté ici** : la qualité de votre compte rendu de
recette initiale, et le raisonnement écrit dans `explication`. Les hypothèses
que vous avez écartées ont leur place dans ce champ : les y écrire ne compte
pas contre vous, c'est ce qu'on attend d'un diagnostic.

## À savoir avant de commencer

Le backend n'est pas à vous : son code est contrôlé, et la réparation d'un
incident se fait autour de lui, dans le proxy ou sur le système.

Pour le test de reprise, la validation détruit `/etc/nginx/conf.d` et les
fichiers `ssl_certificate` et `ssl_certificate_key` que votre configuration
charge. Votre sauvegarde doit donc les couvrir, avec leurs droits.

L'autorité de test perd sa racine à chaque redémarrage, par construction. La
validation garde la racine récupérée avant le redémarrage et ne demande jamais
un autre renouvellement après lui : le certificat sur disque reste valide face
à cette racine.

Le budget est de 150 minutes. Aucun indice n'est donné pendant une session
d'épreuve.
