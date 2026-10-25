# La tâche

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
