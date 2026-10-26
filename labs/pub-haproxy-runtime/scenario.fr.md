# Scénario

Le proxy fonctionne. Son socket d'administration est en **mode 666**, en
`level admin`, et il n'y a aucun fichier d'état. Trois choses en découlent,
et aucune ne casse quoi que ce soit :

1. **N'importe quel compte de la machine peut piloter le proxy.**
   Vérifiez-le, l'identité `intrus` n'appartient à aucun groupe :

   ```bash
   sudo -u intrus sh -c "echo 'show info' | socat -t2 stdio /run/haproxy/admin.sock"
   ```

2. **Lire et agir ne sont pas séparés.** Tout ce qui a besoin de lire l'état,
   un collecteur de métriques, une sonde, un script de supervision, reçoit le
   droit d'agir.

3. **Un rechargement oublie toute décision prise à chaud.** Le serveur que
   vous venez de sortir du service y revient au premier `reload` déclenché
   par autre chose, par exemple un renouvellement de certificat.

Trois identités de test existent : `veilleur` qui doit pouvoir lire,
`exploitant` qui doit pouvoir agir, et `intrus` qui ne doit rien pouvoir.
Tout est décrit dans `/opt/pub-haproxy-runtime/recette.txt`.

## Les quatre contrôles

1. **Seule l'identité prévue dispose des opérations d'administration.** Ce
   contrôle est critique et joue les trois identités : `veilleur` lit et ne
   peut pas agir, `exploitant` agit, `intrus` ne peut ni l'un ni l'autre.
   Aucune opération destructrice n'est jouée : retirer et remettre un serveur
   suffit à prouver le droit.

2. **Le retrait change réellement l'affectation.** L'état rapporté ne suffit
   pas : le test envoie du trafic et lit quelle instance répond. Un serveur
   marqué sortant qui continue de servir est un état, pas une décision.

3. **La décision survit à un rechargement.** Le test retire le serveur,
   recharge, et regarde l'état que HAProxy **rapporte**. Un fichier marqueur
   posé à côté ne répond pas à la demande : c'est HAProxy qui doit se
   souvenir, parce que c'est lui qui décide à qui va la prochaine requête.

4. **Le retour au nominal est documenté et exécuté.** La méthode se livre
   comme un exécutable, parce que la validation la joue : une méthode de
   retour qui n'a jamais été jouée n'est pas une méthode de retour. Le
   dossier, lui, est relu par un humain.
