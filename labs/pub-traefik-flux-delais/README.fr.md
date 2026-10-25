# pub-traefik-flux-delais

**Public :** l'apprenant.

Ajustez les délais et les transports de Traefik pour qu'un backend
légitimement lent réussisse toujours, qu'un backend bloqué en permanence
échoue dans un délai borné au lieu de faire attendre le client
indéfiniment, qu'un WebSocket et un flux SSE survivent à une période
d'inactivité au lieu d'être coupés par un délai de point d'entrée pensé
pour des requêtes ordinaires, qu'un backend malade soit retiré de la
rotation de répartition de charge sans entraîner les backends sains avec
lui, et qu'une politique de retry ne rejoue jamais une action métier non
idempotente déjà réussie côté backend.

## Ce que vous saurez faire

- Configurer les délais de transfert d'un transport serveur pour qu'une
  lenteur bornée réussisse et qu'une panne persistante échoue rapidement,
  au lieu des deux extrêmes.
- Configurer les délais de réponse d'un point d'entrée pour que les flux
  longs (WebSocket, SSE) ne soient pas pris pour une requête HTTP ordinaire
  bloquée.
- Configurer une sonde de santé de répartiteur de charge pour qu'un
  backend malade cesse de recevoir du trafic sans faire échouer les
  requêtes destinées à ses pairs sains.
- Reconnaître pourquoi un middleware de retry appliqué à une écriture non
  idempotente peut dupliquer une action métier, et le cadrer correctement.

Quatre conteneurs backend (deux backends API interchangeables, un backend
de flux, un backend d'action avec un compteur de requêtes) et une instance
Traefik sont préparés. La tâche et les chemins disponibles sont décrits
dans `/opt/pub-flux/README`.
