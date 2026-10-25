# pub-socle-tls

**Public :** l'apprenant.

Apprenez à décider si un point d'accès TLS prouve vraiment l'identité qu'il
revendique, à l'aide d'un magasin de confiance explicitement fourni plutôt
qu'en désactivant la vérification.

## Ce que vous saurez faire

- Vérifier une chaîne de certificats face à une racine de confiance donnée, au
  lieu de faire confiance à ce qui est présenté.
- Distinguer un mauvais nom, une chaîne cassée et un certificat expiré par leur
  échec de vérification réel, pas en devinant.
- Décider, à partir du seul état observé, si un point d'accès doit être
  accepté ou refusé.

Le travail se fait sur `edge.lab` ; `challenge/README.md` décrit le fichier à
produire.
