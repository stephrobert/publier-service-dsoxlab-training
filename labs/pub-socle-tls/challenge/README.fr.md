# La tâche

## La situation

Quatre points d'accès TLS ont été déployés sur `edge.lab` pour répondre sous le
nom `svc.tls.test`. Avant toute publication, une revue de sécurité demande la
preuve que chaque point d'accès est vraiment ce qu'il prétend être, avec la
racine de confiance de test remise pour cette revue, pas le magasin de
confiance public du système.

## Mission

Lisez `/home/student/README-tls`, connectez-vous à chacun des quatre points
d'accès avec le certificat racine fourni, et écrivez
`/home/student/verdict.yaml` indiquant si chaque point d'accès est accepté et,
quand il est refusé, pourquoi : un nom qui ne correspond pas, une chaîne qui ne
remonte pas à la racine fournie, ou des dates qui placent le certificat hors de
sa période de validité. Ne modifiez pas l'horloge de la machine de test pour
cela.

## Ce qui est demandé

1. Lisez `/home/student/README-tls` : quatre points d'accès TLS répondent sur
   `edge.lab` sous le nom `svc.tls.test`, et le seul magasin de confiance à
   utiliser est `/home/student/ca.pem`.
2. Connectez-vous à chacun avec ce magasin et le bon nom, sans jamais
   désactiver la vérification (pas de `-k`, pas de `--insecure`, pas de
   `verify=False`). Identifiez, pour chacun, s'il est accepté et, quand il est
   refusé, la seule cause : un nom qui ne correspond pas, une chaîne qui ne
   remonte pas à `ca.pem`, ou des dates hors de la période de validité.
3. Écrivez `/home/student/verdict.yaml` :

```yaml
verdict:
  positif: {accepte: true,  cause: aucune}
  nom:     {accepte: false, cause: nom}
  chaine:  {accepte: false, cause: chaine}
  date:    {accepte: false, cause: date}
```

`cause` vaut `aucune`, `nom`, `chaine` ou `date` ; `aucune` seulement quand
`accepte` vaut `true`.

Les tests se connectent eux-mêmes aux quatre points d'accès, avec `ca.pem` et
le bon nom, et comparent ce qu'ils observent réellement avec votre verdict.
