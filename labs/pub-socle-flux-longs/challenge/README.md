# The task

On `edge.lab`, edit `/etc/pub-flux/politique.yaml` so that all four
points below hold. Nothing else needs to be written: the tests observe
the WebSocket and the SSE stream directly, with the measuring client
already installed there. The policy is re-read on every message and
every loop of a stream, no restart needed, so editing it takes effect
immediately even on an already-open stream.

```yaml
websocket:
  delai_echo_ms: <how long, in milliseconds, the service waits before
    echoing back a WebSocket message: low enough that a round trip is
    not mistaken for a hang>
sse:
  taille_tampon: <how many notifications the SSE stream holds before
    sending any of them: 1 to forward each one as soon as it exists>
inactivite:
  intervalle_heartbeat_s: <how many seconds the SSE stream waits, with no
    new notification, before sending a heartbeat comment: low enough
    that a client can actually trust a quiet stream is alive>
panne:
  fermer_proprement: <true|false: does the SSE stream send a dedicated
    failure event and close when the producer disappears, instead of
    hanging silently forever?>
```

Read `/home/student/README-flux` for the exact ports in this run. Use the
measuring client to check your own work before relying on the tests:

```sh
sudo -u student python3 /opt/pub-flux/mesure_flux.py websocket <port_ws>
sudo -u student python3 /opt/pub-flux/mesure_flux.py sse <port_sse> <duree_s>
sudo -u student python3 /opt/pub-flux/mesure_flux.py panne <port_sse> <attente_avant_s> <attente_apres_s>
```

The `panne` check stops the producer itself (`sudo systemctl stop
pub-flux-producteur.service`) after the given wait: restart it afterward
(`sudo systemctl start pub-flux-producteur.service`) if you run this by
hand, the tests already do it for you.

The tests run the same checks themselves, from `edge.lab`, timing arrival
on the wire rather than reading a final response body, since that is the
only thing that actually distinguishes a stream from a request.
