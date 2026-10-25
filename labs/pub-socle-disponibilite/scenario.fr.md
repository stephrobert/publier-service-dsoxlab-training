# Scénario

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
