# pub-socle-reverse-proxy

**Public :** l'apprenant.

Apprenez à lire une chaîne de deux proxys inverses comme deux décisions de
confiance distinctes : qui a le droit de dire d'où vient réellement une
requête, et qui a le droit de dire quelle identité elle porte. Une chaîne de
proxys ne vaut que par son point le plus étroit où un client non fiable a
encore la parole : si un maillon en aval croit encore ce que prétend le
maillon précédent, un en-tête forgé voyage jusqu'à l'application sans être
corrigé.

## Ce que vous saurez faire

- Déterminer quel maillon d'une chaîne de proxys termine TLS et lesquels
  relaient en HTTP clair, et le vérifier face au trafic réel plutôt que le
  supposer.
- Expliquer pourquoi l'origine et l'identité d'un client légitime doivent
  être décidées par le proxy réellement en contact avec lui, et non
  simplement reconduites par chaque maillon suivant.
- Démontrer qu'un en-tête `X-Forwarded-For` ou d'identité forgé, injecté
  depuis un client non fiable, n'accorde aucun privilège une fois la chaîne
  corrigée.
- Fermer les chemins directs qui laissent un client atteindre un maillon
  interne ou l'application en contournant toute la chaîne.

Vos observations se font depuis `poste.lab` et `edge.lab` ; le livrable
s'écrit sur `edge.lab`. `challenge/README.md` le décrit précisément.
