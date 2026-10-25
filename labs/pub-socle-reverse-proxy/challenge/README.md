# The task

On `edge.lab`, write `/home/student/diagnostic.yaml`:

```yaml
perimetre_tls: true
interne_tls: false
backend_tls: false
origine_forcee_par_perimetre: <true|false: does the perimetre hop decide the origin itself, instead of repeating whatever the client sent?>
identite_forcee_par_interne: <true|false: does the interne hop decide the identity itself, instead of repeating whatever the request already carried?>
usurpation_sans_privilege: true
contournement_ferme: true
```

Then, still on `edge.lab`:

- Edit `/etc/pub-rp/politique.yaml` so that the perimetre hop always trusts
  its own observation of the client's address instead of an
  `X-Forwarded-For` the client supplied, and so that the interne hop always
  sets its own identity decision instead of repeating one already present
  in the request. Both files are re-read on every request: no restart is
  needed for this change to take effect.
- Edit `/etc/pub-rp/interne.env` and `/etc/pub-rp/backend.env` so that
  neither the interne hop nor the backend application still listens on
  every interface, then restart `pub-rp-interne.service` and
  `pub-rp-backend.service`. Only the perimetre hop is meant to be reachable
  from a client.

The tests query the chain themselves, from `poste.lab` with `--cacert
/home/student/ca.pem` and never `-k`, and from `edge.lab`:

- A normal request, with no forged header, must reach the application with
  the client's real address and the identity `anonyme`.
- A request forging `X-Forwarded-For` to an arbitrary address and `X-User`
  to `admin` must still reach the application with the client's real
  address, the identity `anonyme`, and no reserved data.
- A direct connection to the interne hop's port or the backend's port, from
  `poste.lab`, must fail outright, with or without forged headers.

They compare your file against what they observe; they never trust the
text of your file alone.
