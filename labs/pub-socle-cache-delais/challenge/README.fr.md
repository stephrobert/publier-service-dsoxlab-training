# Scénario

Une passerelle met en cache, rejoue les requêtes en échec et attend le
backend, selon `/opt/pub-socle-cache-delais/politique-cache.yaml`. Cette
politique a été écrite pour aller vite, et elle y arrive.

Elle a aussi quatre défauts, un par contrôle de la validation : elle met
`/prive` en cache, elle ne varie sur rien, elle rejoue les `POST`, et elle
attend un backend mort pendant dix minutes.

Les identités et les routes du banc sont dans
`/home/student/identites-cache.txt`.

## Mission

Corrigez la politique. Le cache doit continuer d'accélérer ce qui peut
l'être, sans jamais servir la donnée d'un utilisateur à un autre, sans
doubler une commande, et sans laisser un appelant attendre indéfiniment.

## Les deux pièges, et pourquoi ils ne se voient pas

**La variation.** Cacher `/public` sans varier sur la langue sert la version
française à qui demande l'anglais. Cacher une route privée sous une clé qui
ne distingue pas l'utilisateur sert les données d'Alice à Bob. Dans les deux
cas, le service est plus rapide et le cache a l'air de marcher.

**Le rejeu.** L'application incrémente son compteur métier **puis** coupe la
connexion sans répondre. L'appelant ne peut donc pas distinguer « l'action
n'a pas eu lieu » de « l'action a eu lieu, la réponse s'est perdue ».
Rejouer dans le doute double la commande, et **seul le compteur le sait** :
le client voit exactement la même chose dans les deux cas.

C'est pourquoi la décision de rejouer se prend sur la **méthode**, et jamais
sur ce qu'on observe.

## Ce qui est vérifié

- une réponse éligible est **réutilisée**, et sa variation respectée.
  `/public` porte un numéro tiré au hasard à chaque passage : deux réponses
  identiques prouvent un cache, deux réponses différentes prouvent qu'il n'y
  en a pas. Aucun en-tête n'est cru sur parole ;
- **critique** : Bob ne reçoit jamais la donnée d'Alice, ni l'inverse ;
- **critique** : une commande envoyée une fois est comptée **une** fois ;
- la lenteur légitime de deux secondes passe, et la panne est bornée. Les
  deux moitiés comptent : une borne qui rejette ce qui marche est une panne
  qu'on s'inflige.

## Indices

- La passerelle relit la politique à chaque requête.
- `cache.varier_sur` liste les en-têtes qui distinguent deux entrées. Un
  en-tête absent de cette liste ne distingue rien.
- Une route privée a deux remèdes, et le plus sûr est le plus simple.
- `delais.lecture` se choisit en mesurant la réponse légitime la plus lente,
  pas en prenant une durée ronde.
