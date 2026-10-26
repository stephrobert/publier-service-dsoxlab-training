# Scénario

La machine porte un HAProxy installé par le paquet de la distribution, et une
configuration qui ne contient **aucun listener** : ni `frontend`, ni `listen`.
HAProxy refuse de démarrer sur une telle configuration, et le message qu'il
rend est la première chose à savoir lire.

Trois services tournent déjà sur la boucle locale. Deux parlent HTTP et
renvoient leur nom, le `Host` reçu et l'adresse que le proxy leur a
transmise. Le troisième ne parle **pas** HTTP : il répond à toute ligne en la
renvoyant préfixée, y compris à une ligne de requête HTTP.

Ce que l'installation doit présenter est écrit dans
`/opt/pub-haproxy-installation/manifeste.txt`. La version y est **relevée sur
le binaire installé**, pas recopiée : elle suit donc la distribution.

## Mission

Publiez les deux noms HTTP sur le port 80 et le service de lignes en relais
TCP sur le port 7001, depuis la même instance. Ouvrez la page d'état et le
socket d'administration, et faites en sorte que ni l'une ni l'autre ne soit
joignable depuis le réseau.

## Les quatre contrôles

1. **Ce qui tourne suit le manifeste.** La version est lue sur le binaire que
   systemd exécute réellement, résolu par `/proc/<pid>/exe`, et non sur le
   premier `haproxy` que le `PATH` propose. `maxconn` et `nbthread`, eux, sont
   lus **par le socket d'administration**, donc sur l'instance vivante : une
   valeur écrite dans un fichier qui n'a jamais été chargé ne compte pas.

2. **Le mode HTTP route les deux noms et transmet l'adresse du client.** Le
   service affiche le `X-Forwarded-For` qu'il a reçu, et le test le compare à
   l'adresse réelle du client. Un en-tête que le proxy se déclarerait à
   lui-même ne prouverait rien : c'est le backend qui témoigne.

3. **Le mode TCP relaie sans comprendre**, et le contrôle se joue dans les
   deux sens. Sur le port 7001, une ligne de requête HTTP volontairement
   invalide doit être **relayée** et revenir en écho. Sur le port 80, la même
   ligne doit être **refusée** par HAProxy avant d'atteindre quoi que ce soit.
   Si les deux ports se comportaient pareil, c'est que les deux frontends sont
   dans le même mode, quelles que soient les directives écrites.

4. **L'état et l'administration ne sont pas publics.** Ce contrôle est
   critique, et il ne lit aucun fichier de configuration : il énumère les
   sockets sur lesquels HAProxy écoute réellement, et n'accepte en dehors de
   la boucle locale que les ports 80 et 7001. Il exige en même temps que la
   page d'état réponde depuis la machine et que le socket d'administration
   réponde à `show info` : on ne satisfait donc pas ce contrôle en supprimant
   ce qu'il surveille.

Le dernier test redémarre la machine, puis rejoue les contrôles 2, 3 et 4.
Un service qui répond aujourd'hui et ne revient pas demain n'est pas
installé, il est lancé.
