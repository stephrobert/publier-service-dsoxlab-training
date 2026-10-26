# Scénario

Deux machines servent le même service, avec la même configuration et **le
même certificat**. Chacune répond par son adresse propre. Rien n'en fait un
seul point d'entrée : l'adresse de service `10.10.110.200` n'appartient à
aucune des deux.

`keepalived` est installé et **non configuré**. Déployer la bascule est la
mission.

Tout est décrit dans `/opt/pub-haproxy-ha/recette.txt`.

## Ce que la fixture a déjà réglé pour vous, et pourquoi

Les deux proxys écoutent sur `:443` et non sur une adresse précise. Une
écoute sur une adresse qui n'existe pas encore refuse de démarrer, et
l'adresse de service n'existe sur aucune des deux machines au repos. C'est
le piège le plus commun de cette famille, et il est évité ici pour que vous
travailliez sur la bascule plutôt que sur un service qui ne démarre pas.

## Les quatre contrôles

1. **Les deux points d'entrée servent la recette.** Chacun par son adresse
   propre, en TLS strict, avant toute bascule. Une paire dont un membre ne
   sert pas n'est pas une paire, c'est une machine et un témoin.

2. **La perte d'un processus, puis celle d'un hôte, provoquent une reprise
   mesurée.** La validation arrête HAProxy sur la machine qui porte
   l'adresse, puis redémarre cette machine entière. Dans les deux cas elle
   sonde **sans rien changer côté client** : c'est toute la différence entre
   une bascule et une intervention.

   Le premier cas est le plus instructif. Une bascule qui ne surveille que
   la machine ne voit pas un proxy mort sur une machine vivante : l'adresse
   reste où elle est, et le service est à terre avec une haute disponibilité
   qui se porte bien.

3. **La politique et les certificats restent cohérents.** Contrôle
   critique. Les deux points d'entrée présentent la **même empreinte** de
   certificat, et la route privée reste refusée **après** la bascule. Une
   politique qui ne suit pas le service est une ouverture qui s'ignore.

4. **Le dossier décrit ce que cette bascule ne protège pas.** Relu par un
   humain. Trois sujets sont attendus, et aucun ne se lit dans la
   configuration : la partition réseau et le double maître qu'elle produit,
   l'état qui n'est pas répliqué, et ce que la bascule ne couvre pas du
   tout.
