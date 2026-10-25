# pub-socle-flux-longs

**Public :** l'apprenant.

Apprenez pourquoi un flux n'est pas une requête : un corps qui n'arrive
jamais avant la fin, un événement qui arrive groupé avec neuf autres, une
connexion qui se tait sans jamais confirmer qu'elle est toujours vivante,
un backend qui disparaît sans un mot. Rien de tout cela n'est visible à
un outil qui lit une réponse une fois qu'elle est complète, parce que tout
l'intérêt d'un flux est justement de ne jamais se compléter tant qu'on
continue à l'écouter.

## Ce que vous saurez faire

- Chronométrer un aller-retour WebSocket après la poignée de main et
  reconnaître quand un délai artificiel, pas le réseau, est la cause d'un
  écho lent.
- Lire des Server-Sent Events au fur et à mesure de leur arrivée, un par
  un, et distinguer une politique de tampon qui retient les événements
  d'une politique qui les transmet dès qu'ils existent.
- Choisir un intervalle de heartbeat qui se déclenche réellement assez
  souvent pour qu'un client puisse faire confiance à un flux silencieux
  mais vivant, plutôt qu'un intervalle si long qu'il n'existe presque
  pas.
- Rendre explicite, sur le flux qu'elle alimente, une panne backend,
  avec un événement dédié et une fermeture propre, plutôt que de laisser
  le client attendre sur une connexion à laquelle plus personne ne
  répondra jamais.

Vos observations se passent sur `edge.lab`, avec le client de mesure
fourni ; `challenge/README.md` décrit la tâche précisément.
