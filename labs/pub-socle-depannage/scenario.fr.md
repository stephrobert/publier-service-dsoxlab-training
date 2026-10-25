# Scénario

`depan.test` répond sur `edge.lab`, en TLS, derrière un routeur qui relaie
vers un backend protégé. Quelqu'un signale qu'il se comporte mal. Personne
ne vous dit quelle couche : cela peut être le nom, le chemin réseau, le
certificat, la configuration de la route, ou le processus du backend
lui-même. Le journal porte aussi un avertissement sans rapport, qui
inquiète mais ne mène nulle part.

## Mission

Observez depuis `poste.lab`, le client indépendant, et depuis `edge.lab`,
côté opérateur. Formulez une hypothèse, testez-la, et nommez la couche et
le composant réellement fautifs, pas une supposition plausible. Réparez
par la plus petite correction qui fonctionne, puis prouvez que le service
répond à nouveau et qu'aucune protection, la route interdite, l'isolement
du backend, ou TLS lui-même, n'a été affaiblie au passage.
