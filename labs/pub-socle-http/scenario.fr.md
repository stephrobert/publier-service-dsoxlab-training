# Scénario

Une API de commandes tourne sur `edge.lab`. L'équipe cliente signale deux
ennuis : certaines commandes créées à travers une redirection arrivent sous la
mauvaise forme, et après une coupure réseau la même commande apparaît deux
fois. On vous demande la recette de l'API avant la mise en service du client.

## Mission

Lisez `/home/student/README-api`, envoyez la requête de recette qu'il décrit,
consignez dans `/home/student/recette-http.yaml` ce que fait chaque redirection
à un POST et ce que renvoie chaque route d'erreur, puis écrivez
`/home/student/envoyer-commande.sh`, un client qui envoie une commande sans
jamais la créer deux fois, même quand la réponse est perdue.
