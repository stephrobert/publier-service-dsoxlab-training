# Scénario

`service.mes.test` vient de vous être confié, en service sur `edge.lab` :
une seule route métier derrière du TLS, servie par deux origines, une
active et une candidate pour une future bascule. Le seul contrôle déjà fait
dessus, c'est qu'elle démarre.

Personne n'a encore exécuté de vraie matrice de recette depuis le client,
DNS compris. Personne n'a non plus essayé de restaurer sa configuration et
son état depuis la sauvegarde posée juste à côté ; une sauvegarde dont
personne n'a jamais restauré est une croyance, pas un fait. Et personne n'a
jamais fait revenir une bascule défaillante en arrière dessus, cache
compris.

## Mission

Réceptionnez vraiment cette publication, depuis `poste.lab`, le client
indépendant. Prouvez ensuite, sur `edge.lab`, que vous savez la perdre et la
récupérer, et défaire une bascule défaillante sans attendre l'expiration de
son cache. Terminez par un compte rendu honnête de ce que cette recette doit
encore à une vraie mise en service exposée sur Internet.

