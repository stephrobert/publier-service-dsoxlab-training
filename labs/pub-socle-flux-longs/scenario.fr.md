# Scénario

Un service de notifications tourne sur `edge.lab`, tout en boucle locale
(`127.0.0.1`, le client de mesure tourne sur ce même hôte). Il expose un
WebSocket (un point d'écho) et un flux SSE (Server-Sent Events) alimenté
par un petit service producteur, qui émet une notification par seconde
tant qu'il tourne. La configuration livrée porte quatre erreurs à la
fois : chaque écho WebSocket est retardé de trois secondes, le flux SSE
met en tampon cinquante événements avant d'en envoyer un seul,
l'intervalle de heartbeat est réglé si haut qu'il ne se déclenche jamais
en pratique, et une panne du producteur laisse le flux SSE ouvert et
silencieux pour toujours au lieu de la signaler.

## Mission

Lisez `/home/student/README-flux`, puis éditez
`/etc/pub-flux/politique.yaml` (relu à chaque message et à chaque tour de
boucle d'un flux, sans redémarrage nécessaire) pour que :

- un message WebSocket revienne en écho en moins d'une seconde ;
- les événements de données SSE arrivent un par un au fur et à mesure de
  leur production, pas groupés ;
- le flux SSE émette un heartbeat en quelques secondes, pas en milliers ;
- quand le producteur est arrêté, le flux SSE envoie un événement de
  panne dédié puis se ferme, au lieu de pendre silencieusement.

Utilisez le client de mesure fourni, `/opt/pub-flux/mesure_flux.py`, pour
observer chacun de ces points en chronométrant l'arrivée, pas en lisant
un corps final.
