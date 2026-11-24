# La tâche

## La situation

Un service web est publié sur `edge.lab` et répond correctement. Avant la mise
en service, une revue de sécurité constate qu'il a été lancé dans la précipitation :
l'application et son interface d'administration écoutent aussi largement que le
point d'entrée. N'importe qui sur le réseau pourrait contourner le point
d'entrée et leur parler directement.

## Mission

Lisez `/home/student/README-exposition`, découvrez ce qui écoute réellement sur
`edge.lab` et écrivez la matrice de flux dans `/home/student/flux.yaml`. Fermez
ensuite tous les chemins qui contournent le point d'entrée : le service public
reste joignable depuis `poste.lab`, alors que le backend et l'administration ne
le sont que depuis `edge.lab` elle-même.

## Ce qui est demandé

1. Découvrez quels ports écoutent sur `edge.lab` et qui peut les joindre, depuis
   `edge.lab` elle-même et depuis `poste.lab`.
2. Écrivez `/home/student/flux.yaml` avec une entrée par service (`public`,
   `backend`, `admin`), donnant son port et s'il est joignable (`ouvert`) ou non
   (`ferme`) depuis le client et depuis l'hôte lui-même :

```yaml
flux:
  public:  {port: <n>, client: <ouvert|ferme>, local: <ouvert|ferme>}
  backend: {port: <n>, client: <ouvert|ferme>, local: <ouvert|ferme>}
  admin:   {port: <n>, client: <ouvert|ferme>, local: <ouvert|ferme>}
```

3. Modifiez le système pour que la matrice décrive la politique du README : le
   service public est joignable depuis le client, le backend et l'administration
   ne le sont pas, et les trois restent joignables depuis `edge.lab`.
   Si vous utilisez `nft`, placez vos règles dans la table `inet pub_expo`.

Les tests sondent eux-mêmes les trois ports, depuis `poste.lab` et depuis
`edge.lab`, et comparent votre matrice à ce qu'ils observent.
