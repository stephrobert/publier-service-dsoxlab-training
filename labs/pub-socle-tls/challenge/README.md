# The task

## The situation

Four TLS endpoints were deployed on `edge.lab` to answer under the name
`svc.tls.test`. Before anything is published, a security review asks for proof
that each endpoint really is what it claims to be, using the test root of
trust that was handed over for this review, not the operating system's public
trust store.

## Mission

Read `/home/student/README-tls`, connect to each of the four endpoints with
the given root certificate, and write `/home/student/verdict.yaml` stating
whether each endpoint is accepted and, when it is refused, why: a name that
does not match, a chain that does not lead back to the given root, or dates
that place the certificate outside its validity window. Do not change the
test machine's clock to do this.

## What is asked

1. Read `/home/student/README-tls`: four TLS endpoints answer on `edge.lab`
   under the name `svc.tls.test`, and the only trust store you must use is
   `/home/student/ca.pem`.
2. Connect to each endpoint with that trust store and the right name, without
   ever disabling verification (no `-k`, no `--insecure`, no
   `verify=False`). Identify, for each one, whether it is accepted and, when
   it is refused, the single reason: a name that does not match, a chain that
   does not lead back to `ca.pem`, or dates outside the validity window.
3. Write `/home/student/verdict.yaml`:

```yaml
verdict:
  positif: {accepte: true,  cause: aucune}
  nom:     {accepte: false, cause: nom}
  chaine:  {accepte: false, cause: chaine}
  date:    {accepte: false, cause: date}
```

`cause` is one of `aucune`, `nom`, `chaine`, `date`; `aucune` only when
`accepte` is `true`.

The tests connect to the four endpoints themselves, with `ca.pem` and the
expected name, and compare what they really observe with your verdict.
