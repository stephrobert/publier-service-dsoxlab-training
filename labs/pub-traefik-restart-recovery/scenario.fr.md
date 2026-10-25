# Scénario

Le service web de `edge.lab` tourne dans un conteneur Docker, mais après le
redémarrage du moteur Docker il reste indisponible jusqu'à une intervention
manuelle. Il doit repartir automatiquement et répondre sur
`http://edge.lab:18080/`.

## Mission

Rendez le service disponible avant et après un redémarrage du moteur Docker,
sans intervention manuelle.
