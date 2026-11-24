# Scénario

La pile était saine. Une panne a été injectée, tirée au hasard parmi cinq
familles : le routage, la sonde de santé, la confiance TLS vers le backend,
une limite de trafic, ou une saturation. **Vous ne savez pas laquelle.**

Du bruit a été posé par-dessus, et il n'explique rien : un frontend pour un
nom abandonné, un fichier de notes d'exploitation, un serveur déclaré en
panne exprès. Lire `/etc/haproxy/notes-exploitation.txt` fait partie du
travail.

La recette décrit l'état sain attendu :
`/opt/pub-haproxy-depannage/recette.txt`.

## Deux canaris, et ils font partie de l'état sain

C'est le point le plus important de ce lab.

- **`/api-usurpe/`** mène à un backend dont le certificat est signé par une
  autorité étrangère et qui porte **le même nom** que le légitime. Il sert
  le même marqueur. Il doit **rester refusé** : son refus est la preuve que
  la vérification TLS du backend est stricte.

- **`sonde-cassee`** est un serveur vivant dont la readiness échoue en
  permanence et dont les routes utiles rendent 500. Il doit **rester hors
  service**.

Aucun des deux ne fait partie de la panne. Les désactiver, l'un en retirant
`verify required`, l'autre en retirant les sondes, ferait repartir le
service et retirerait la garantie en même temps. C'est exactement ce que le
troisième contrôle mesure, et c'est la tentation de toute astreinte à trois
heures du matin.

## Les quatre contrôles

1. **Le dossier nomme la cause et la distingue de son symptôme.** Un 503
   n'est pas une cause : c'est ce que le proxy répond quand il n'a plus de
   serveur, et au moins trois des cinq familles le produisent. Le dossier
   est relu par un humain ; le test vérifie seulement qu'il existe et qu'il
   sépare les deux.

2. **Le service et les routes saines sont restaurés.** La matrice est
   rejouée depuis le client indépendant, avec un jeton par mesure.

3. **Les vérifications ne sont pas désactivées.** Contrôle critique : les
   deux canaris doivent tenir leur rôle **après** votre correction.

4. **L'administration et les backends restent injoignables.** Contrôle
   critique aussi, et mesuré dans les deux sens : rien de tout cela ne
   répond depuis le client, et tout répond depuis la machine.
