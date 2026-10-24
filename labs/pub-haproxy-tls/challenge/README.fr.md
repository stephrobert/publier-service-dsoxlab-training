# Défi : émettre et renouveler un certificat HAProxy

## Critères

- `app.lab.test` publie le backend attendu en HTTPS.
- Les requêtes HTTP reçoivent une redirection permanente vers HTTPS.
- HAProxy sert un certificat pour `app.lab.test` émis par Pebble, puis sert
  un nouveau certificat après renouvellement.
- La clé du compte ACME possède le mode `0600`.
- TLS 1.2 fonctionne ; TLS 1.0 et TLS 1.1 sont refusés.
- Le renouvellement ne redémarre pas HAProxy et le service reste disponible.

Le client ACME natif de HAProxy est expérimental. Le corrigé de référence ne
figure pas dans les guides.
