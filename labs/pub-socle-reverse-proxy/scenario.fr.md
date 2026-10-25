# Scénario

Une vitrine sur `edge.lab` est atteinte à travers deux proxys inverses : un
premier qui reçoit réellement la connexion venue de l'extérieur, et un
second derrière lui qui relaie vers l'application. L'application journalise,
pour chaque requête, l'adresse qu'on lui a demandé de retenir et l'identité
qu'on lui a demandé de retenir. Lors d'un audit, quelqu'un a remarqué que
ces deux valeurs étaient simplement celles envoyées par le client d'origine,
transmises sans correction par les deux maillons. Rien n'était cassé à
proprement parler : TLS avait réussi, la chaîne répondait. Mais une requête
venue de l'internet public pouvait prétendre provenir d'un réseau interne,
et pouvait prétendre être un administrateur, et l'application n'avait aucun
moyen de faire la différence.

On vous demande de comprendre exactement quel maillon est responsable de
décider ce qu'il faut croire, et de vous assurer que rien de tout cela ne
peut plus être forgé depuis l'extérieur de la chaîne.

## Mission

Lisez `/home/student/README-rp` sur `edge.lab`, puis produisez, toujours sur
`edge.lab`, `/home/student/diagnostic.yaml` : les faits que vous avez
établis par l'observation sur le maillon qui termine TLS, ceux qui relaient
en HTTP clair, et sur la façon dont l'origine et l'identité circulent
actuellement dans la chaîne. Fermez ensuite le chemin décrit ci-dessus,
ainsi que tout chemin direct qui laisserait encore un client atteindre un
maillon qu'il n'était jamais censé atteindre.

L'autorité de test est déjà installée sur `poste.lab`, dans
`/home/student/ca.pem`.
