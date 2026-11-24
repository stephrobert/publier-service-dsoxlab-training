# La tâche

## La situation

Une route métier tourne sur edge.lab, derrière un pipeline de journaux et un
exportateur de métriques tous les deux parfaitement sains : l'équipe
précédente s'est assurée que la collecte elle-même ne tombe jamais en panne.
Personne, en revanche, n'a jamais écrit ce que signifie vraiment l'indicateur
de niveau de service, réglé l'alerte contre une vraie panne, ni appris à la
supervision à distinguer une panne réelle d'une nuit calme. L'astreinte qui a
ouvert le tableau de bord actuel n'a pas pu dire si le silence de la nuit
dernière signifiait que tout allait bien, ou que personne ne regardait.

## Mission

Lisez `/home/student/README-obs`, puis, sur edge.lab :

- Écrivez `/home/student/sli.yaml` : la route, les exclusions et les codes de
  succès qui définissent le SLI.
- Modifiez `/etc/pub-obs/politique.yaml` (relu en continu, aucun redémarrage
  nécessaire) pour que l'alerte se déclenche sur une vraie panne que vous
  injecterez et revienne à la normale une fois celle-ci retirée, et pour que
  l'évaluateur distingue une vraie panne, une absence de trafic et une
  collecte bloquée, au lieu de les confondre.
- Écrivez `/home/student/correlation.yaml` : le backend et la durée que vous
  trouvez dans le journal des accès pour l'incident déjà journalisé et nommé
  dans le README.

## Ce qui est demandé

1. Écrivez `/home/student/sli.yaml` :

```yaml
route: /commande
exclut: [/sante]
code_min_succes: 200
code_max_succes: 299
```

Les tests appliquent exactement ces champs au journal des accès réel, à la
fois sur un lot historique connu et sur un lot frais qu'ils génèrent
eux-mêmes, et comparent le résultat à la définition correcte.

2. Sur `edge.lab`, modifiez `/etc/pub-obs/politique.yaml` (relu en continu,
   aucun redémarrage nécessaire) :

```yaml
collecte:
  staleness_max_s: <n>
trafic:
  seuil_minimum: <n>
alerte:
  seuil_taux_erreur: <0..1>
```

Les tests lisent `http://127.0.0.1:<port>/diagnostic` sur l'évaluateur (port
donné dans `/home/student/README-obs`) en injectant, un à la fois :

- une vraie panne (le drapeau `panne` décrit dans le README) : l'évaluateur
  doit classer `panne_reelle` avec `firing: true`, puis revenir à la normale
  une fois le drapeau retiré ;
- un générateur de trafic arrêté : il doit classer `absence_trafic`, jamais
  `panne_reelle` ;
- un exportateur de métriques gelé : il doit classer `collecte_perdue` une
  fois votre seuil de fraîcheur franchi, ni trop vite ni jamais.

3. Écrivez `/home/student/correlation.yaml` pour l'incident nommé dans le
   README :

```yaml
requete_id: <l'identifiant de l'incident>
backend: pub-obs-metier
code: <le code trouvé dans le journal>
duree_ms: <la latence trouvée dans le journal>
```

Les tests lisent eux-mêmes la même ligne de journal et la comparent à votre
fichier.
