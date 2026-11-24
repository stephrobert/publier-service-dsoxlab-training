# La tâche

## La situation

Deux applications sont publiées derrière la même adresse et le même port sur
`edge.lab` : `boutique.dht.test`, une vitrine publique, et
`compte.dht.test`, où les clients gèrent leur compte. Chacune a son propre
nom, son propre certificat et son propre backend. Un visiteur qui avait reçu
le mauvais lien s'est un jour retrouvé devant l'application de gestion de
compte alors que le navigateur affichait toujours un cadenas et les détails
du certificat de la vitrine, que personne n'avait regardés de près. Rien
n'était cassé : TLS avait réussi, la chaîne de certification était
authentique. L'application derrière n'était simplement pas celle que le
visiteur, ou le cadenas, laissait supposer.

On vous demande de comprendre exactement pourquoi, et de vous assurer qu'un
troisième nom, qui n'a jamais été enregistré nulle part, ne peut plus
atteindre l'une ou l'autre application par accident.

## Mission

Lisez `/home/student/README-dht` sur `edge.lab`, puis produisez, toujours sur
`edge.lab`, `/home/student/diagnostic.yaml` : les faits que vous avez établis
par l'observation, depuis `poste.lab` et depuis `edge.lab`, sur la résolution
DNS, le choix du certificat TLS et le routage applicatif HTTP. Fermez ensuite
le chemin décrit ci-dessus.

L'autorité de test est déjà installée sur `poste.lab`, dans
`/home/student/ca.pem`.

## Ce qui est demandé

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
