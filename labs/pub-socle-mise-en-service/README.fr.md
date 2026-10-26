# pub-socle-mise-en-service

**Public :** l'apprenant.

La réception est le moment où une mise en service cesse d'être la vôtre pour
devenir le problème du client : une fois acceptée, « ça ne marche pas »
devient votre incident, pas un nouveau test. Ce lab vous fait jouer les deux
rôles de cette passation sur la même publication, `service.mes.test`,
exposée en TLS sur `edge.lab`.

## Ce que vous saurez faire

- Écrire et exécuter une matrice de recette depuis un client indépendant
  (`poste.lab`) : DNS, TLS, la route métier et la route interdite, sans
  contourner la résolution DNS pour le contrôle DNS lui-même.
- Restaurer configuration et état actifs depuis une sauvegarde après en
  avoir perdu la copie active, et prouver que le service restauré répond
  avec la vraie valeur métier, pas une valeur par défaut.
- Faire revenir une mise en service à une origine connue bonne après une
  bascule défaillante, en tenant compte d'un cache qui n'oublie pas de
  lui-même une décision périmée.
- Dire par écrit ce qui, dans cette recette, n'était que simulé, et quelles
  preuves une vraie mise en service exposée sur Internet exigerait encore.
