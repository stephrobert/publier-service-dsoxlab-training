# Scénario

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
