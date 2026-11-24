# La mission

## La situation

Vous reprenez le point d'entrée d'une petite plateforme sur `edge.lab`.
HAProxy est installé et n'a **aucune mission** : ni listener, ni certificat, ni
route. Deux services tournent déjà derrière lui, démarrés à la hâte : un
**catalogue** et un service de **notifications**. Personne ne les a publiés
correctement, et personne n'a jamais essayé de perdre le point d'entrée puis
de le récupérer. Une autorité de certification de test et un client ACME sont
fournis.

Sur la même machine, une seconde instance HAProxy nommée **archives** sert
une application depuis un moment. Elle fonctionnait. Puis quelque chose s'est
cassé, et personne ne dit quoi.

On vous donne un besoin et une recette, jamais une configuration à recopier :
`/opt/pub-epreuve-haproxy/recette.txt` dit ce qui doit arriver, et pas une
directive.

## Mission

**Partie 1, livrer deux services.** Publiez le catalogue et le service de
notifications derrière HAProxy, chacun sous son nom, en HTTPS, avec un
certificat par nom que vous obtenez et renouvelez par un script que vous
écrivez. Contrôlez l'accès aux routes d'administration. Faites en sorte
qu'un client ne choisisse pas l'adresse que les services voient pour lui, et
qu'un client qui envoie trop soit ralenti puis relâché. Laissez passer un flux
d'événements long. Rendez le proxy observable. Fermez tout ce qui contourne le
point d'entrée. Puis prouvez que vous savez perdre HAProxy, sa configuration et
la donnée métier, et tout récupérer depuis des sauvegardes.

**Partie 2, diagnostiquer une panne inconnue.** L'instance archives porte une
panne tirée au sort parmi cinq familles. Trouvez laquelle, réparez-la **sans
retirer aucune protection**, et consignez ce que vous avez trouvé.

## Ce que la machine note, et ce qu'un relecteur lit

Vingt contrôles de cinq points, joués depuis `poste.lab`, le client
indépendant, sous vérification TLS stricte (jamais `curl -k`).

| Domaine | Contrôles | Points |
|---|---|---|
| Publication et protocoles | cycle de certificats, HTTPS par nom, nom inconnu et redirection, chargement vérifié | 20 |
| Sécurité et confiance | isolement des backends, administration, adresse source, limitation de débit, clés privées | 25 |
| Observabilité et flux | flux long, métriques, service arrêté lu dans les métriques, refus comptés | 20 |
| Diagnostic | famille et composant, service réparé, confiance et sondes conservées, limite et borne conservées | 20 |
| Reprise et retour arrière | restauration complète, rechargement sans coupure, redémarrage | 15 |

Une machine ne sait pas juger un raisonnement. Les champs `famille` et
`composant` de `incident.yaml` sont comparés à la panne posée ; le champ
`explication` est **lu par un relecteur**, et seule sa présence est vérifiée
ici. Le relecteur lit aussi votre configuration et vos scripts, et vous demande
de justifier vos choix.

## Règles de l'épreuve

- L'autorité de test délivre des certificats valables **cinq minutes**. La
  validation exécute votre script de renouvellement chaque fois qu'il lui faut
  un certificat frais.
- L'autorité de test tire une nouvelle racine et oublie ses comptes à chaque
  démarrage. La validation relit la racine avant chaque contrôle.
- Une correction qui retire une protection pour rétablir le service (couper la
  vérification, retirer les sondes, lever une limite) ne compte pas : les
  contrôles qui suivent la réparation cherchent ces protections.
- Le dernier contrôle redémarre la machine, puis rejoue la recette. Tout doit
  revenir seul.

## Ce qui est demandé

Travaillez depuis `poste.lab` pour tout ce que voit un client, et depuis
`edge.lab` pour tout ce que fait un opérateur. `/home/student/racine-acme.pem`
sur `poste.lab` est la racine de l'autorité de test : n'utilisez jamais
`curl -k` / `--insecure`. Lisez en entier `/home/student/README-epreuve` et
`/opt/pub-epreuve-haproxy/recette.txt` sur `edge.lab` : ils disent ce qui doit
arriver.

L'épreuve a deux parties indépendantes. Budget de temps : 150 minutes.

1. **Livrer deux services (domaines : publication, sécurité, observabilité,
   reprise).** HAProxy est installé et n'a aucune mission. Les services
   `catalogue` et `notifications` tournent sur les ports 18301 et 18302,
   démarrés à la hâte. Livrez, avec la configuration de HAProxy et deux
   scripts :

   - les deux noms en HTTPS, un certificat par nom, obtenus auprès de
     l'autorité de test par le client ACME fourni ;
   - `/opt/pub-epreuve-haproxy/renouveler`, exécutable, qui renouvelle les deux
     certificats et les met en service sans redémarrer HAProxy. La validation
     l'**exécute**, plusieurs fois, et de nouveau après un redémarrage ;
   - les exigences de la recette sur l'accès, l'adresse source, la limitation
     de débit, l'isolement, le flux et les métriques ;
   - la sauvegarde de votre configuration dans
     `/var/backups/pub-epreuve-haproxy/haproxy.cfg.bak`, et
     `/opt/pub-epreuve-haproxy/restaurer`, exécutable, qui restaure la donnée
     métier du catalogue **et** la configuration de HAProxy depuis les
     sauvegardes, puis remet HAProxy en service. La validation casse les trois,
     puis l'exécute.

2. **Diagnostiquer une panne inconnue (domaine : diagnostic).** L'instance
   `archives` (port 8088, sa propre configuration, son unité et son socket,
   listés dans la recette) porte une panne tirée parmi cinq familles. Réparez-la
   sans retirer aucune protection, puis écrivez `/home/student/incident.yaml`
   sur `edge.lab` :

   ```yaml
   famille: routage    # un parmi : routage, sonde, confiance, limite, delai
   composant: "..."
   explication: "..."
   ```

   Nommez la cause réelle, appuyée sur ce que vous avez observé. Citer toutes
   les familles « au cas où » n'est pas un diagnostic. Les hypothèses que vous
   avez écartées ont leur place dans `explication`.
