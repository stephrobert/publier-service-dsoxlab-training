# La tâche

Sur `edge.lab`, écrivez `/home/student/diagnostic.yaml` :

```yaml
resolveur: <adresse IP du résolveur réellement interrogé par poste.lab pour dht.test>
nom_inconnu_resout: <true|false : la résolution DNS normale répond-elle pour le nom inconnu ?>
sni_boutique: boutique.dht.test
sni_compte: compte.dht.test
host_decide_routage: <true|false : est-ce l'en-tête HTTP Host, et non le SNI TLS, qui décide quelle application répond ?>
application_si_sni_boutique_host_compte: <"boutique"|"compte" : avec SNI=boutique.dht.test et Host: compte.dht.test, quelle application répond ?>
nom_inconnu_doit_etre_refuse: true
```

Puis, toujours sur `edge.lab`, modifiez `/etc/pub-dht/routes.yaml` pour qu'un
nom que personne n'a enregistré (ni dans le DNS, ni dans ce fichier) soit
franchement refusé, au lieu d'atteindre en silence l'application déclarée en
premier.

Les tests interrogent eux-mêmes le routeur, depuis `poste.lab` avec
`--cacert /home/student/ca.pem` et jamais `-k`, en faisant varier SNI et Host
indépendamment, et sondent séparément le nom inconnu. Ils comparent votre
fichier à ce qu'ils observent, et vérifient que le nom inconnu est vraiment
refusé, pas seulement décrit comme tel.
