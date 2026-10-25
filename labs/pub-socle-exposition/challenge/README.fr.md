# La tâche

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
