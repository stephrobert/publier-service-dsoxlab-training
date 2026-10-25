# Scenario

`depan.test` answers on `edge.lab`, in TLS, behind a router that forwards to
a protected backend. Someone reports it is misbehaving. Nobody has told you
which layer: it could be the name, the network path, the certificate, the
route configuration, or the backend process itself. The journal also
carries an unrelated warning that looks alarming but leads nowhere.

## Mission

Observe from `poste.lab`, the independent client, and from `edge.lab`, the
operator side. Form a hypothesis, test it, and name the actual faulty layer
and component, not a plausible guess. Repair it with the smallest change
that fixes it, then prove the service works again and that no protection,
the forbidden route, the backend's isolation, or TLS itself, was weakened
along the way.
