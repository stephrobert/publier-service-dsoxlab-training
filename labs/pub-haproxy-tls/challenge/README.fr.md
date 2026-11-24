# Défi : émettre et renouveler un certificat HAProxy

## La situation

Une petite application écoute sur l'hôte, mais le déploiement HAProxy fourni
ne publie pas correctement le service en HTTPS. L'autorité ACME Pebble et son
répondeur de défi HTTP-01 sont déjà préparés.

## Mission

Configurez HAProxy 3.4 pour router `app.lab.test` vers le backend local,
rediriger HTTP vers HTTPS et obtenir le certificat avec son client ACME natif.
Protégez la clé du compte ACME et prouvez qu'un certificat renouvelé est servi
sans interrompre le processus proxy.

Le support ACME natif est expérimental dans HAProxy 3.4 et exige
`expose-experimental-directives`. Le corrigé de référence ne figure pas dans
les guides.

## Ce qui est demandé

### Critères

- `app.lab.test` publie le backend attendu en HTTPS.
- Les requêtes HTTP reçoivent une redirection permanente vers HTTPS.
- HAProxy sert un certificat pour `app.lab.test` émis par Pebble, puis sert
  un nouveau certificat après renouvellement.
- La clé du compte ACME possède le mode `0600`.
- TLS 1.2 fonctionne ; TLS 1.0 et TLS 1.1 sont refusés.
- Le renouvellement ne redémarre pas HAProxy et le service reste disponible.

Le client ACME natif de HAProxy est expérimental. Le corrigé de référence ne
figure pas dans les guides.
