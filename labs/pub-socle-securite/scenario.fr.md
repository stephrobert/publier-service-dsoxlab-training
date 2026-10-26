# Scénario

Un service publie trois routes : `/` est publique, `/compte` est réservée à
un utilisateur connecté, `/admin` à l'administration. Elles sont servies par
un garde paramétrable, qui applique à la lettre le fichier
`/opt/pub-socle-securite/politique.yaml`.

Cette politique est **vide**. Le garde l'applique donc fidèlement : tout
passe, tout en-tête d'identité est cru, et le journal conserve tout ce qu'il
reçoit, mots de passe compris.

Les identités de test sont dans `/home/student/identites.txt`.

## Mission

Écrivez la politique. Elle doit laisser passer le trafic légitime, refuser
les autres sur les routes sensibles, résister au contournement, et cesser
d'écrire des secrets sur le disque.

## Ce qui est vérifié, et pourquoi jamais une directive

Une politique se juge sur ce que le service **répond**, pas sur ce qu'elle
déclare : un fichier peut nommer une règle que le garde n'applique à rien,
parce qu'elle vise un préfixe qui ne correspond à aucune route. La
validation envoie donc de vraies requêtes depuis `poste.lab`, le client
indépendant, et lit le **statut** et le **corps**.

Lire le corps n'est pas du luxe. Un 200 qui renvoie la page publique sur
`/admin` n'est pas une fuite ; un 200 qui renvoie « revocation des acces »
en est une. Le statut seul ne les distingue pas.

Quatre contrôles, dont trois critiques :

1. **Le légitime passe.** Les trois catégories autorisées obtiennent leur
   contenu. C'est l'ancrage : refuser tout le monde satisferait les trois
   autres contrôles en supprimant le service.
2. **Les routes sensibles refusent**, et le corps du refus ne porte pas le
   contenu protégé.
3. **Ni l'origine directe ni un en-tête forgé ne contournent.**
   L'application répond encore sur son port, depuis le réseau client : une
   politique posée devant une porte qu'on peut contourner ne protège rien.
   Et un `X-Identite` envoyé par l'appelant lui-même ne vaut pas une
   identité.
4. **Aucun secret semé ne survit.** La validation envoie une valeur
   sentinelle dans `Cookie` et `Authorization`, puis la cherche dans le
   journal et dans le dossier. Elle vérifie aussi que le journal n'est pas
   vide : effacer n'est pas ne rien journaliser.

## Indices

- Le garde relit la politique à chaque requête : aucun redémarrage n'est
  nécessaire pour la voir agir.
- Deux gestes ferment l'accès direct, et les deux sont acceptés : lier
  l'application à la boucle locale, ou refuser son port depuis l'extérieur.
- `proxys_de_confiance` est ce qui sépare un en-tête posé par un proxy
  légitime d'un en-tête forgé par n'importe qui.
