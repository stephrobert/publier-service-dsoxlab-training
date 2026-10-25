# pub-socle-dns-http-tls

**Public :** l'apprenant.

Apprenez pourquoi un certificat valide et vérifié ne prouve pas que vous avez
atteint la bonne application : TLS choisit un certificat à partir du SNI
envoyé pendant la poignée de main, puis HTTP choisit l'application à partir de
l'en-tête Host envoyé ensuite, et ce sont deux décisions séparées. Apprenez
aussi à distinguer une résolution DNS normale d'une résolution qui contourne
délibérément le DNS, et pourquoi un nom que personne n'a enregistré ne doit
jamais atteindre une application par accident.

## Ce que vous saurez faire

- Comparer une résolution DNS normale à une résolution forcée qui contourne
  le résolveur.
- Faire varier le SNI en conservant la même adresse, et vérifier la chaîne et
  le SAN du certificat reçu sans désactiver la vérification.
- Faire varier l'en-tête HTTP Host en conservant le même SNI, et expliquer
  quelle application répond réellement.
- Fermer le chemin qui laisse un nom que personne n'a enregistré atteindre une
  application par accident.

Vos observations se font depuis `poste.lab` et `edge.lab` ; le livrable
s'écrit sur `edge.lab`. `challenge/README.fr.md` le décrit précisément.
