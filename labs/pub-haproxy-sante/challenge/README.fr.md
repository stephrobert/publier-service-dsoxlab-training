# Scénario

Deux backends servent la même application derrière HAProxy. Ils sont à poids
égaux, et **personne ne les surveille** : ni `option httpchk`, ni `check`, ni
poids déclarés. Un backend qui tombe reste donc dans la rotation.

Constatez-le avant d'écrire quoi que ce soit :

```bash
echo casse > /opt/pub-haproxy-sante/etat-beta
for i in $(seq 6); do curl -s -o /dev/null -w '%{http_code} ' http://127.0.0.1/; done
echo pret > /opt/pub-haproxy-sante/etat-beta
```

Chaque backend expose `/ready`, et son état se pilote par un fichier que vous
possédez. L'état `casse` dégrade les deux : la sonde rend 503 **et** les
requêtes utiles rendent 500. C'est la situation qu'une sonde de readiness
existe pour couvrir, celle d'un service vivant dont une dépendance est tombée.

Les poids et les seuils sont prescrits dans
`/opt/pub-haproxy-sante/recette.txt`. Ils ne sont pas laissés à votre choix
parce que la validation mesure des **fenêtres** : un retrait doit avoir lieu,
et une panne plus courte que le seuil ne doit pas en provoquer. Sans seuils
connus, ces deux mesures n'auraient aucune référence.

## Mission

Déclarez la sonde et ses seuils, les poids, et montrez que vous savez retirer
un backend du service sans couper ce qu'il sert déjà.

## Les quatre contrôles

1. **En état sain, chacun prend la part que son poids lui donne.** Mesuré sur
   un échantillon, et confirmé par la table d'état : le test exige que la
   sonde soit de **niveau 7** (`L7OK`), et non une simple ouverture de
   connexion. Un `check` seul vérifie qu'un port accepte, ce que fait aussi un
   service qui a perdu sa base de données.

2. **Un backend vivant dont la readiness échoue est retiré.** La fenêtre est
   calculée depuis les seuils de la recette, et le test lit le compteur de
   transitions de HAProxy lui-même : il exige **une** descente, pas un état.
   Après convergence, plus aucune erreur ne doit atteindre le client.

3. **Une panne plus courte que le seuil ne retire rien.** C'est le contre-test,
   et c'est la moitié qui compte : une sonde réglée trop court transforme
   chaque hoquet en bascule, et la bascule coûte plus que le hoquet. Le test
   exige que des sondes aient **échoué** et qu'aucune descente n'ait eu lieu.
   Sans cette seconde moitié, `fall 1` passerait le contrôle 2 haut la main.

4. **Le drainage arrête les nouvelles affectations sans couper l'établi.** Un
   flux long est ouvert sur le serveur visé, puis le serveur est drainé. Les
   nouvelles requêtes ne doivent plus l'atteindre, et le flux doit continuer
   jusqu'à son terme. C'est la différence entre drainer et arrêter, et c'est
   elle qui permet une maintenance sans coupure visible.
