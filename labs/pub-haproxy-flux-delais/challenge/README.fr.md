# Scénario

Une API derrière HAProxy, avec deux instances, des sessions en mémoire, un
flux d'événements et un WebSocket. Quatre choses sont fausses.

1. **Toutes les bornes valent la même chose, et il n'y a pas de borne de
   file.** Une connexion qui ne répond jamais, une file pleine et une réponse
   lente prennent le même temps et rendent le même signal. Un exploitant ne
   peut donc pas dire laquelle des trois il regarde, ce qui est exactement ce
   qu'on lui demande à trois heures du matin.

2. **Dix secondes d'inactivité, et aucune borne de tunnel.** Le flux
   d'événements meurt entre deux battements, et le WebSocket meurt dans un
   silence parfaitement normal. Le battement de l'application est lent à
   dessein : c'est le silence entre deux événements qui met une borne
   d'inactivité à l'épreuve.

3. **Le proxy rejoue tout ce qui peut l'être.** Une écriture dont la réponse
   s'est perdue **après** que le serveur l'a traitée est donc rejouée, et le
   travail a lieu deux fois. Le client, lui, n'a rien reçu : il ne peut pas
   le savoir.

4. **Aucune politique de session.** Une requête sur deux change d'instance,
   et l'état que le client croit avoir n'y est pas.

Les bornes attendues sont dans `/opt/pub-haproxy-flux-delais/recette.txt`.
Elles sont **différentes les unes des autres**, et c'est le point.

## Les quatre contrôles

1. **Chaque phase lente a sa propre borne.** Les trois injections sont jouées
   séparément : une adresse qui ne répond pas, un serveur dont la seule place
   est prise, et une réponse plus lente que sa borne. Le test mesure les trois
   **durées** et exige qu'elles soient distinctes et que chacune corresponde à
   sa borne. Trois durées identiques, c'est une seule borne déguisée en trois.

2. **Les flux longs tiennent la durée annoncée.** Le flux d'événements doit
   rendre plusieurs événements horodatés espacés du battement, et le
   WebSocket doit encore répondre après la durée demandée, sans avoir rien
   échangé entre-temps.

3. **La politique de session tient, et ses limites sont dites.** Vingt
   lectures consécutives doivent trouver la session. Puis le test **retire du
   service** l'instance qui la détient, et vérifie que la session est perdue :
   c'est le comportement attendu, pas un défaut. Coller un client à une
   instance n'est pas répliquer son état, et le dossier doit le dire.

4. **Aucune écriture n'est dupliquée.** Ce contrôle est critique. Le point
   d'écriture compte l'écriture **puis ferme sans répondre** : le travail a
   eu lieu, le client ne le sait pas. Après une seule tentative, le compteur
   métier doit valoir exactement un.

   La moitié qui compte vient ensuite : une **lecture** dont la connexion
   échoue doit encore aboutir. Restreindre les réessais ne consiste pas à les
   supprimer, sinon la configuration a perdu sa tolérance aux pannes en
   gagnant sa sûreté.
