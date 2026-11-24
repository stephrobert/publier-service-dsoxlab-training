# Obtenir un certificat automatiquement avec ACME

## La situation

Vous êtes sur `edge.lab`. Dans `/opt/pub-lab`, lancez un serveur ACME de test
(Pebble) et obtenez un certificat pour `app.lab.test` avec lego, par le défi
HTTP-01. `LISEZ-MOI.txt` donne les images (déjà tirées, épinglées par digest)
et les chemins que les tests lisent.

## Un certificat que personne n'a tapé à la main

Vous travaillez dans `/opt/pub-lab` sur `edge.lab`.

### Ce qui est attendu

1. Pebble tourne en conteneur, sans le raccourci « toujours valide », et
   répond sur `https://localhost:14000/dir` ; son API de gestion répond sur
   `https://localhost:15000`.
2. `/opt/pub-lab/lego/certificates/app.lab.test.crt` existe, est émis par ce
   Pebble (sa chaîne se vérifie contre les racines que Pebble sert), nomme
   `app.lab.test`, et correspond à sa clé privée.
3. La validation a réellement eu lieu : le journal de Pebble montre le défi
   HTTP-01 pour `app.lab.test`.

### Ce qui est prouvé

Les tests interrogent Pebble et le certificat, jamais votre fichier Compose.
