# La tâche

Sur `edge.lab`, éditez `/etc/pub-flux/politique.yaml` pour que les quatre
points ci-dessous tiennent. Rien d'autre n'est à écrire : les tests
observent directement le WebSocket et le flux SSE, avec le client de
mesure déjà installé là-bas. La politique est relue à chaque message et
à chaque tour de boucle d'un flux, sans redémarrage nécessaire : l'éditer
prend effet immédiatement, même sur un flux déjà ouvert.

```yaml
websocket:
  delai_echo_ms: <combien de millisecondes le service attend avant de
    renvoyer un message WebSocket en écho : assez bas pour qu'un
    aller-retour ne soit pas pris pour un blocage>
sse:
  taille_tampon: <combien de notifications le flux SSE retient avant
    d'en envoyer une seule : 1 pour transmettre chacune dès qu'elle
    existe>
inactivite:
  intervalle_heartbeat_s: <combien de secondes le flux SSE attend, sans
    nouvelle notification, avant d'envoyer un commentaire de heartbeat :
    assez bas pour qu'un client puisse réellement faire confiance à un
    flux silencieux mais vivant>
panne:
  fermer_proprement: <true|false : le flux SSE envoie-t-il un événement
    de panne dédié puis se ferme-t-il quand le producteur disparaît, au
    lieu de pendre silencieusement pour toujours ?>
```

Lisez `/home/student/README-flux` pour les ports exacts de cette session.
Utilisez le client de mesure pour vérifier votre propre travail avant de
vous reposer sur les tests :

```sh
sudo -u student python3 /opt/pub-flux/mesure_flux.py websocket <port_ws>
sudo -u student python3 /opt/pub-flux/mesure_flux.py sse <port_sse> <duree_s>
sudo -u student python3 /opt/pub-flux/mesure_flux.py panne <port_sse> <attente_avant_s> <attente_apres_s>
```

La vérification `panne` arrête elle-même le producteur (`sudo systemctl
stop pub-flux-producteur.service`) après l'attente donnée : redémarrez-le
ensuite (`sudo systemctl start pub-flux-producteur.service`) si vous
l'exécutez à la main, les tests le font déjà pour vous.

Les tests font les mêmes vérifications eux-mêmes, depuis `edge.lab`, en
chronométrant l'arrivée sur le fil plutôt qu'en lisant un corps de réponse
final, puisque c'est la seule chose qui distingue réellement un flux
d'une requête.
