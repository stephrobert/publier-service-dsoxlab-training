# Scénario

HAProxy tourne, quatre backends sont sains, et la table de routage est
fausse. Les quatre fautes sont de la même famille, et c'est le sujet du lab :
**aucune des quatre lignes n'est fausse en elle-même.**

1. La ligne qui consulte la table des noms est placée **avant** les
   exceptions de chemin. HAProxy retient la première règle qui correspond,
   donc les exceptions sont écrites, lisibles, justes, et jamais atteintes.
2. `path_beg /panier` attrape aussi `/panierarchive` et `/panier-public`. Un
   préfixe n'est pas un chemin.
3. `/api/v2/` est routé vers l'API, qui ne le sert pas : la route le fait
   répondre comme s'il existait.
4. `default_backend panier` fait du panier la destination de tout nom
   imprévu, y compris ceux qu'un tiers choisit.

La table à obtenir est écrite dans `/opt/pub-haproxy-routage/recette.txt`.
Elle dit ce qui doit arriver, jamais avec quelles directives l'obtenir.

## Ce qui mesure, et pourquoi ce n'est pas la réponse rendue

Chaque backend **compte les requêtes qu'il sert** et le dit sur la boucle
locale. La validation lit ces compteurs avant et après chaque requête.

C'est nécessaire : une route qui fuit ne se voit pas dans la réponse. Un
`default_backend panier` répond 200, avec un corps plausible, pour n'importe
quel nom. Seul le backend peut dire qu'il a servi cette requête, et ni la
configuration ni le client ne peuvent le dire à sa place.

## Les quatre contrôles

1. **Chaque combinaison de nom et de chemin atteint le backend prévu.** La
   matrice porte les chemins voisins à dessein, et chaque requête est comptée
   chez le backend attendu, et chez lui seul.

2. **Un nom imprévu n'atteint aucun backend.** Ce contrôle est critique, et
   il est mesuré sur les compteurs : refuser en répondant 404 tout en ayant
   joint un backend ne compte pas.

   Attention à ce qu'il ne dit pas : un **chemin** imprévu sous un nom connu
   n'est pas refusé. La table donne à chaque nom une route par défaut, et
   c'est elle qui s'applique. Ce sont les **noms** qui n'ont pas de route par
   défaut, et `/api/v2/`, qui est nommément refusé.

3. **La table se change à chaud, et ne survit pas au rechargement.** La
   validation modifie une entrée par le socket d'administration, vérifie que
   le routage suit, recharge, puis vérifie que le routage est **revenu** à ce
   que dit le fichier. Les deux moitiés comptent : la première prouve que la
   map décide vraiment, au lieu d'être décorative à côté d'ACL qui tranchent ;
   la seconde est la raison pour laquelle un changement à chaud se recopie
   toujours dans le fichier.

4. **Un dossier explique l'ordre des décisions.** Il est relu par un humain,
   et son raisonnement n'est pas noté. Le test vérifie seulement qu'il existe
   et qu'il traite les deux cas qu'on ne peut pas trancher sans avoir regardé :
   les chemins voisins de `/panier`, et `/api/v2/`.
