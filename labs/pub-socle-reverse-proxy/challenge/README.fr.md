# La tâche

## La situation

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

## Ce qui est demandé

Sur `edge.lab`, écrivez `/home/student/diagnostic.yaml` :

```yaml
perimetre_tls: true
interne_tls: false
backend_tls: false
origine_forcee_par_perimetre: <true|false : le maillon périmètre décide-t-il lui-même l'origine, au lieu de reconduire ce que le client a envoyé ?>
identite_forcee_par_interne: <true|false : le maillon interne décide-t-il lui-même l'identité, au lieu de reconduire celle déjà portée par la requête ?>
usurpation_sans_privilege: true
contournement_ferme: true
```

Puis, toujours sur `edge.lab` :

- Modifiez `/etc/pub-rp/politique.yaml` pour que le maillon périmètre fasse
  toujours confiance à sa propre observation de l'adresse du client plutôt
  qu'à un `X-Forwarded-For` fourni par celui-ci, et pour que le maillon
  interne impose toujours sa propre décision d'identité plutôt que de
  reconduire celle déjà présente dans la requête. Les deux fichiers sont
  relus à chaque requête : aucun redémarrage n'est nécessaire pour que ce
  changement s'applique.
- Modifiez `/etc/pub-rp/interne.env` et `/etc/pub-rp/backend.env` pour
  qu'aucun des deux, ni le maillon interne ni l'application backend,
  n'écoute plus sur toutes les interfaces, puis redémarrez
  `pub-rp-interne.service` et `pub-rp-backend.service`. Seul le maillon
  périmètre est censé être joignable depuis un client.

Les tests interrogent eux-mêmes la chaîne, depuis `poste.lab` avec
`--cacert /home/student/ca.pem` et jamais `-k`, et depuis `edge.lab` :

- Une requête normale, sans en-tête forgé, doit atteindre l'application
  avec l'adresse réelle du client et l'identité `anonyme`.
- Une requête forgeant `X-Forwarded-For` vers une adresse arbitraire et
  `X-User` vers `admin` doit toujours atteindre l'application avec
  l'adresse réelle du client, l'identité `anonyme`, et aucune donnée
  réservée.
- Une connexion directe au port du maillon interne ou à celui du backend,
  depuis `poste.lab`, doit échouer franchement, avec ou sans en-tête forgé.

Ils comparent votre fichier à ce qu'ils observent ; ils ne font jamais
confiance au seul texte de votre fichier.
