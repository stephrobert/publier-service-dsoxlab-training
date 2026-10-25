# pub-socle-disponibilite

**Public :** l'apprenant.

Apprenez pourquoi « il a deux instances » n'est pas la même affirmation
que « il survit à en perdre une ». Un répartiteur qui ne répartit en
réalité jamais le trafic entre les deux backends sains, une sonde de
santé si lente et si tolérante qu'elle mettrait des minutes à remarquer
une vraie panne, et le même angle mort au retour : rien de tout cela ne
se voit en lisant un fichier de configuration, seulement en cassant
vraiment quelque chose et en chronométrant ce qui suit.

## Ce que vous saurez faire

- Prouver, en échantillonnant du trafic réel, qu'un répartiteur étale
  vraiment les requêtes sur chaque backend qu'il tient pour sain, plutôt
  que de coller au premier qui répond.
- Choisir un intervalle de sonde et un seuil d'échec qui retirent un
  backend malade dans une fenêtre que vous pouvez réellement défendre,
  plutôt qu'une fenêtre si lente qu'elle équivaut à jamais.
- Choisir un seuil de retour qui ramène un backend sain sans attendre
  éternellement, tout en restant assez haut pour résister à une seule
  sonde capricieuse.
- Énoncer, honnêtement et depuis une vraie mesure, ce qu'un seul
  exemplaire de répartiteur ne peut pas survivre : sa propre panne.

Vos observations se passent sur `edge.lab`, avec le sondeur fourni ;
`challenge/README.md` décrit la tâche précisément.
