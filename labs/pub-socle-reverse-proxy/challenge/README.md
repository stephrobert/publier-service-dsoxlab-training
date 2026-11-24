# The task

## The situation

A storefront on `edge.lab` is reached through two reverse proxies: a first
one that actually receives the connection from the outside, and a second
one behind it that forwards to the application. The application logs, for
every request, the address it was told to trust and the identity it was
told to trust. During an audit, someone noticed that both of these were
simply whatever the original client had sent, carried unchanged through
both hops. Nothing had been technically broken: TLS had succeeded, the
chain answered. But a request coming from the public internet could claim
to originate from an internal network, and could claim to be an
administrator, and the application had no way to tell the difference.

You are asked to understand exactly which hop is responsible for deciding
what to trust, and to make sure none of this can be forged from outside the
chain again.

## Mission

Read `/home/student/README-rp` on `edge.lab`, then produce, still on
`edge.lab`, `/home/student/diagnostic.yaml`: the facts you established by
observation about which hop terminates TLS, which ones relay in plain
HTTP, and how origin and identity currently flow through the chain. Then
close the path described above, and every direct path that still lets a
client reach a hop it was never meant to reach.

The test authority is already installed on `poste.lab`, at
`/home/student/ca.pem`.

## What is asked

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
