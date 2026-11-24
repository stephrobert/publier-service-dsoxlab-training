# La tâche

## La situation

Deux instances identiques de backend tournent sur `edge.lab`, tout en
boucle locale (`127.0.0.1`, le sondeur fourni tourne sur ce même hôte),
derrière un unique répartiteur opaque. La configuration livrée porte
trois erreurs à la fois : le répartiteur n'alterne en réalité jamais
entre les deux backends tant qu'ils répondent tous les deux, l'intervalle
de sa sonde de santé et son seuil d'échec sont réglés si haut que retirer
un backend malade prendrait des minutes, et le seuil de retour est tout
aussi lent au retour.

## Mission

Lisez `/home/student/README-disp`, puis éditez
`/etc/pub-disp/politique.yaml` (relue à chaque sonde et à chaque
requête, sans redémarrage nécessaire) pour que :

- un échantillon de trafic via le répartiteur, les deux backends étant
  sains, atteigne réellement les deux ;
- un backend marqué malade (via un fichier de drapeau, simulant une
  panne applicative) soit retiré de la rotation dans une fenêtre
  raisonnable ;
- une fois rétabli, il revienne dans la rotation dans une fenêtre
  raisonnable ;
- arrêter le répartiteur lui-même, seul point d'entrée de cette
  topologie, prouve honnêtement ce qu'un seul exemplaire ne peut pas
  survivre, alors que chaque backend reste joignable directement.

Utilisez le sondeur fourni, `/opt/pub-disp/sonder.py`, pour observer
chacun de ces points depuis une vraie requête HTTP vers le bon point
d'entrée, pas une supposition sur un produit précis.

## Ce qui est demandé

Sur `edge.lab`, éditez `/etc/pub-disp/politique.yaml` pour que les quatre
points ci-dessous tiennent. Rien d'autre n'est à écrire : les tests
observent directement le répartiteur et les backends, avec le sondeur
déjà installé là-bas. La politique est relue à chaque sonde et à chaque
requête, sans redémarrage nécessaire.

```yaml
repartition:
  actif: <true|false : le répartiteur alterne-t-il réellement entre
    chaque backend qu'il tient pour sain, au lieu de toujours coller au
    premier qui répond ?>
probe:
  intervalle_s: <combien de secondes entre deux sondes de santé : assez
    bas pour que retirer ou rétablir un backend se produise dans une
    fenêtre que vous pouvez défendre>
  echecs_avant_retrait: <combien de sondes consécutives en échec avant
    qu'un backend sain soit retiré de la rotation : assez bas pour
    réagir, assez haut pour ne pas sur-réagir à une seule sonde
    capricieuse>
  succes_avant_retour: <combien de sondes consécutives réussies avant
    qu'un backend retiré revienne dans la rotation : même compromis, au
    retour>
```

Lisez `/home/student/README-disp` pour les ports exacts de cette session.
Utilisez le sondeur fourni pour vérifier votre propre travail avant de
vous reposer sur les tests :

```sh
sudo -u student python3 /opt/pub-disp/sonder.py echantillon <port_repartiteur> <n>
sudo -u student python3 /opt/pub-disp/sonder.py direct <port_backend>
sudo -u student python3 /opt/pub-disp/sonder.py indisponible <port>
```

Simulez une panne applicative d'un backend avec
`sudo touch /var/lib/pub-disp/malsain-a` (ou `-b`) ; retirez le fichier
pour le rétablir.

Les tests font les mêmes vérifications eux-mêmes, depuis `edge.lab`, y
compris arrêter le répartiteur pour prouver ce qu'un seul exemplaire ne
peut pas survivre ; ils le redémarrent ensuite dans tous les cas.
