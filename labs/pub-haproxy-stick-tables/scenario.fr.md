# Scénario

Une stick-table est déjà en place, dans un backend qui ne sert rien d'autre.
Elle se remplit, elle se lit très bien, et elle ne protège de rien. Trois
choses sont fausses :

1. **La clé suivie est un en-tête que le client envoie.** Chacun choisit donc
   son propre compteur, et il suffit d'en changer pour repartir de zéro.
   Vérifiez-le :

   ```bash
   for v in un deux trois; do curl -s -o /dev/null -H "X-Client-Id: $v" http://127.0.0.1/; done
   echo 'show table compteurs' | sudo socat -t2 stdio /run/haproxy/admin.sock
   ```

2. **Le seuil n'est jamais atteint.** La règle de refus existe, elle est
   juste, et elle ne se déclenche pas.

3. **La fenêtre et l'expiration sont le même nombre.** Ce sont deux bornes
   différentes : l'une dit sur combien de temps la cadence est mesurée,
   l'autre combien de temps une entrée survit à sa dernière requête. Les
   confondre est la façon la plus commune de croire mesurer une cadence quand
   on mesure une durée de vie.

Ce que la table doit compter, avec ses bornes et son seuil, est écrit dans
`/opt/pub-haproxy-stick-tables/recette.txt`.

## Les quatre contrôles

1. **La table compte le bon objet, sur la bonne fenêtre.** Le test envoie un
   nombre connu de requêtes depuis le client et lit les compteurs par le
   socket : la clé doit être **l'adresse du client**, et la cadence doit
   valoir ce qui a été envoyé. Puis il attend la fenêtre et exige que la
   cadence retombe à zéro, ce qui mesure la fenêtre et non le comptage.

2. **Le dépassement refuse, et seul le dépassement.** Une rafale de `seuil`
   requêtes doit **passer** : un contrôle plus strict que ce qui est demandé
   est aussi une faute. Au-delà, le refus est un 429, et il est reproductible.
   Pendant ce refus, une **autre source** doit continuer d'être servie, sinon
   la limite ne protège pas le service, elle le remplace.

3. **La clé ne peut pas être choisie par le client.** Ce contrôle est
   critique. Une fois la source bloquée, le test rejoue la requête avec cinq
   valeurs d'en-tête différentes : toutes doivent rester refusées.

   La moitié qui compte vient ensuite : après la fenêtre, la même source doit
   **retrouver** le service. Un blocage qui ne se lève pas n'est pas une
   limite de cadence, c'est un bannissement, et ce n'est pas ce que la recette
   demande.

4. **Les bornes de mémoire sont celles annoncées.** La taille déclarée est
   lue dans la table, et l'expiration est mesurée pour de vrai : après
   l'expiration, l'entrée doit avoir **disparu** de la table, et pas seulement
   être retombée à zéro. C'est la différence entre les deux bornes, vue de
   l'autre côté.

   Un dossier complète ce contrôle, relu par un humain : il doit dire ce que
   cette table **ne protège pas**. Deux limites au moins sont attendues, et
   elles ne se devinent pas en lisant la configuration.
