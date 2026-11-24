# La tâche

## La situation

Le service web de `edge.lab` tourne dans un conteneur Docker, mais après le
redémarrage du moteur Docker il reste indisponible jusqu'à une intervention
manuelle. Il doit repartir automatiquement et répondre sur
`http://edge.lab:18080/`.

## Mission

Rendez le service disponible avant et après un redémarrage du moteur Docker,
sans intervention manuelle.

## Ce qui est demandé

Faites répondre le service web `whoami` de `edge.lab:18080` en HTTP avant et
après le redémarrage du moteur Docker. Les tests inspectent la politique de
redémarrage du conteneur et appellent le véritable endpoint après le
redémarrage de Docker.

La référence d'image préparée et le répertoire de travail sont décrits dans
`/opt/pub-restart/README`.
