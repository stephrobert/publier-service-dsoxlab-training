# Scénario

Traefik sur `edge.lab` expose quatre backends derrière les noms d'hôte
`api.flux.lab.test`, `flux.lab.test` et `action.flux.lab.test` : deux
backends API interchangeables répartis en charge ensemble, un backend de
flux servant un écho WebSocket et un flux d'événements SSE, et un backend
d'action qui incrémente un compteur à chaque écriture réussie. En l'état,
les délais de transfert du transport serveur sont si généreux qu'un
backend qui ne répond jamais laisse le client attendre des minutes au lieu
d'obtenir un échec clair et borné. Le délai de réponse du point d'entrée
est calibré pour de courtes requêtes ordinaires et coupe silencieusement
les connexions WebSocket et SSE après une courte période d'inactivité,
alors même qu'elles fonctionnent exactement comme prévu. Le répartiteur de
charge n'a aucune sonde de santé : un backend qui cesse d'être prêt
continue de recevoir sa part de trafic au lieu d'être retiré de la
rotation, et les backends sains finissent par absorber des échecs qui
n'étaient jamais les leurs. Enfin, un middleware de retry enveloppe
aveuglément toutes les routes, y compris la route d'action : si la réponse
du backend se perd juste après qu'il a durablement écrit son effet de
bord, Traefik rejoue silencieusement la même requête, et le backend compte
l'action deux fois.

## Mission

Bornez les délais de transfert du transport serveur pour qu'une réponse
légitimement lente réussisse toujours et qu'un backend qui ne répond
jamais échoue en quelques secondes au lieu de faire attendre le client.
Augmentez le délai de réponse du point d'entrée pour qu'une connexion
WebSocket ou SSE inactive ne soit pas prise pour une requête bloquée, sans
désactiver entièrement la protection. Ajoutez une sonde de santé au
répartiteur de charge pour qu'un backend malade soit retiré rapidement de
la rotation, sans jamais faire échouer les requêtes destinées à son pair
sain. Enfin, retirez (ou cadrez correctement) la politique de retry sur la
route d'action pour qu'une réponse perdue ne fasse jamais compter deux fois
la même action métier au backend.
