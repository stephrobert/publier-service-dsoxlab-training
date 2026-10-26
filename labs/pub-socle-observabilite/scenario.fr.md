# Scénario

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
