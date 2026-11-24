# Scénario

Le proxy publie un service en HTTPS, parle à son backend en TLS, et tout
répond. **C'est exactement le problème.**

Quatre choses sont fausses, et aucune ne produit d'erreur :

1. Le backend est joint en TLS avec la vérification **désactivée**. La
   liaison est chiffrée et l'identité du correspondant n'est pas regardée.
   La route `/api-usurpe/` le démontre : elle mène à un backend dont le
   certificat est signé par une **autorité étrangère** et qui porte **le même
   nom** que le légitime. Il sert le même marqueur, donc sa réponse est
   indiscernable d'un succès.

2. Aucune identité cliente n'est demandée. La route `/prive/` est donc
   publique.

3. `option forwardfor` **ajoute** à l'en-tête reçu au lieu de le remplacer.
   Un client qui envoie son propre `X-Forwarded-For` voit sa valeur arriver
   **en premier** chez l'application, qui lit presque toujours la première.

4. L'écoute qui accepte le protocole PROXY est ouverte à tout le réseau. Un
   client peut donc déclarer l'adresse qu'il veut par un autre chemin.

Les deux dernières sont la même faute vue de deux côtés. Fermer l'une laisse
l'autre ouverte, et c'est pour cela qu'elles sont posées ensemble.

Quatre autorités distinctes sont fournies, décrites avec les routes et les
identités dans `/opt/pub-haproxy-confiance/recette.txt`.

## Mission

Rebranchez la chaîne de confiance, dans les deux sens et sur les deux
identités : celle du backend, celle du client, et celle de la source.

## Les quatre contrôles

1. **L'identité du backend est vérifiée, et l'imposteur refusé.** Ce contrôle
   est critique. Le canari `/api-usurpe/` doit passer en **502** et y rester :
   son refus est la preuve que la vérification est stricte, donc le retirer
   reviendrait à retirer la preuve. La route légitime, elle, doit continuer de
   répondre : refuser tout n'est pas vérifier.

2. **Une identité cliente valide est distinguée d'une absence et d'une autre
   autorité.** Critique aussi, et mesuré avec les trois cas : sans
   certificat, avec celui d'une autorité étrangère, et avec celui de
   l'autorité des clients. La route publique doit rester ouverte sans
   identité : la recette demande une autorisation de route, pas un portail.

3. **Un client ne peut pas choisir son adresse.** Critique, et mesuré des
   deux côtés : un en-tête envoyé par le client ne doit pas atteindre
   l'application, et l'écoute qui fait confiance au protocole PROXY ne doit
   pas être joignable depuis le réseau.

   La moitié qui compte est la troisième mesure : depuis la source approuvée,
   une adresse déclarée **doit** arriver jusqu'à l'application. Sans elle, le
   contrôle se satisferait de supprimer l'écoute, et la configuration aurait
   perdu une capacité au lieu de gagner un contrôle.

4. **La route autorisée conserve protocole et identité jusqu'à
   l'application.** Le backend renvoie ce qu'il a reçu, et le test lit ses
   valeurs : le protocole d'origine, l'adresse du client, et le nom porté par
   le certificat client. Sans ce renvoi, il faudrait croire le proxy sur
   parole.
