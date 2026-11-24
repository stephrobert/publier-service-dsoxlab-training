# Scénario

L'application est publiée en HTTP sur le port 80, et c'est tout. Il n'y a
aucun certificat, aucun `bind ssl`, et **aucune route pour le défi ACME**.

Sont fournis :

- une autorité de certification de test, qui délivre des certificats valides
  **cinq minutes** afin que le renouvellement soit observable tout de suite ;
- un **client ACME externe**, enveloppé dans un exécutable pour que vous
  l'appeliez sans cérémonie. Son serveur de défi écoute déjà sur la boucle
  locale ; ce qui manque est la route qui mène le défi jusqu'à lui ;
- la racine de cette autorité, pour que vos vérifications soient strictes.

Tout est décrit dans `/opt/pub-haproxy-tls-stable/recette.txt`.

## Mission

Servez les deux noms en HTTPS, **chacun avec son propre certificat**, et
livrez un script `renouveler` qui refait le cycle de bout en bout.

Un seul certificat portant les deux noms en SAN ne répond pas à la recette.
Le lab porte sur la sélection par SNI, et deux certificats distincts sont le
seul moyen de la mesurer : le contre-test présente le certificat d'un nom et
le fait valider contre l'autre, ce qui doit échouer.

## Les quatre contrôles

1. **L'identité des deux noms est validée strictement.** Chaîne et nom
   d'hôte, avec la racine de l'autorité, et sans jamais désactiver la
   vérification. Le contre-test est la moitié qui compte : un certificat qui
   couvrirait les deux noms passerait la vérification stricte des deux côtés,
   et le contre-test le refuserait. Ce contrôle est critique.

2. **Le cycle produit un nouveau certificat.** La validation **exécute votre
   script** `renouveler`, puis compare le numéro de série et la date de fin
   réellement servis avant et après. Un cycle ne se constate pas après coup :
   il se joue.

   Seconde moitié : la validation pousse elle-même un certificat
   **volontairement invalide** par le socket d'administration et exige qu'il
   soit **refusé**, le service continuant de présenter le précédent. C'est ce
   qui distingue un chargement vérifié d'un chargement : HAProxy valide le
   matériel avant de le mettre en service, et refuse plutôt que de tomber.

3. **Les clés et le compte sont protégés, et absents des sorties.** Tout
   fichier qui porte une clé privée doit être illisible par les autres, et
   aucune clé ne doit apparaître dans les journaux ni dans le journal
   systémique. Ce contrôle est critique : une clé dans un journal est une clé
   publiée, et la rotation ne la rattrape pas.

4. **Le cycle reste opérant après rechargement puis redémarrage.** Les deux
   événements sont joués, et le renouvellement est **rejoué après le
   redémarrage**. Ce contrôle est critique et vient en dernier, puisqu'il
   coupe la machine. Un cycle qui dépendait d'un répertoire sous `/run` ou
   d'une variable d'environnement de votre session se voit là, et nulle part
   avant.
