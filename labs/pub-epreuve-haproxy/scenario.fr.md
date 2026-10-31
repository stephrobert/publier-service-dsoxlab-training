# Scénario

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
