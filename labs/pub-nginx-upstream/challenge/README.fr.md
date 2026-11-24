# Scénario

Deux backends identifiables servent la même application derrière Nginx, et
la configuration fournie porte **trois** défauts : le second backend est
déclaré `backup`, donc il ne sert que si le premier échoue ; `max_fails=0`
**désactive** la détection passive ; et `proxy_next_upstream` porte
`non_idempotent`, ce qui autorise le rejeu d'un `POST`.

Le banc et son pilotage sont décrits dans `/opt/pub-nginx-upstream/banc.txt`.

## Mission

Répartissez vers les deux backends, donnez à la détection passive des
seuils que vous savez justifier, et corrigez la politique de rejeu.

## Ce que le build open source sait faire, et ce qu'il ne sait pas

Nginx open source n'a **aucune sonde active** : il n'ira jamais interroger
un backend pour savoir s'il va bien. La seule détection disponible est
passive, par `max_fails` et `fail_timeout`, et elle apprend des requêtes
des clients eux-mêmes.

Conséquence directe, et c'est le point du lab : **les premières requêtes
partent bel et bien sur le backend fautif** avant qu'il ne soit retiré. La
validation mesure donc qu'il **cesse** d'en recevoir, pas qu'il n'en a
jamais reçu. Exiger zéro requête fautive serait exiger de cet outil ce
qu'il ne sait pas faire, et pousserait à écrire une configuration qui ment.

## Ce qui est vérifié

- les deux backends reçoivent du trafic en état sain ;
- un backend mis en erreur **cesse d'être sollicité**. La mesure est prise
  **sur le backend**, dans `vus-a.txt`, et non chez le client : le rejeu
  rattrape le 502 sur l'autre backend, si bien que le client reçoit un 200
  qu'il y ait eu retrait ou non. Compter les erreurs du client ne mesurerait
  pas la détection, mais le rattrapage ;
- une fois redevenu sain, il **revient** dans la rotation. Le contrôle exige
  d'abord qu'il ait été **retiré** : là où rien n'est jamais retiré, « il est
  revenu » est vrai sans que rien n'ait eu lieu. Un retrait définitif n'est
  pas une détection, c'est une suppression ;
- **critique** : une commande envoyée n'est jamais comptée deux fois. Le
  backend du banc incrémente le compteur **avant** de savoir s'il répondra :
  en mode erreur, il a donc écrit puis échoué, et c'est exactement la
  situation où un rejeu double l'action. Le compteur est le seul témoin, le
  client recevant une erreur dans les deux cas.

## Indices

- `max_fails` et `fail_timeout` se déclarent sur la ligne `server` de
  l'`upstream`. `max_fails=0` signifie « ne jamais retirer », et `backup`
  sur cette même ligne signifie « ne sers que si le premier échoue ».
- `fail_timeout` sert deux fois : c'est la fenêtre pendant laquelle les
  échecs sont comptés, et le délai au bout duquel le backend est retenté.
- `proxy_next_upstream` décide de ce qui est rejoué. Son défaut ne rejoue
  pas les requêtes non idempotentes, et `non_idempotent` lève précisément
  cette protection.
