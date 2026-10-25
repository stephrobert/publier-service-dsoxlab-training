# Scenario

`service.mes.test` has just been handed to you, running on `edge.lab`: a
single business route behind TLS, backed by two origins, one active and one
candidate for a future switch. The only prior check on it was "it starts".

Nobody has run a real acceptance matrix from the client's side yet, DNS
included. Nobody has tried restoring its configuration and state from the
backup that sits next to it, either; a backup nobody has restored from is a
belief, not a fact. And nobody has ever rolled a bad switch back on it,
cache included.

## Mission

Receive this publication for real, from `poste.lab`, the independent
client. Then prove, on `edge.lab`, that you can lose it and get it back, and
that you can undo a bad switch without waiting out its cache. Close with an
honest account of what this acceptance still owes to a real, Internet-facing
release.

