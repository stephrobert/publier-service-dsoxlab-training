# La tâche

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
