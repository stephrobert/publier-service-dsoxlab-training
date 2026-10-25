# Scénario

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
