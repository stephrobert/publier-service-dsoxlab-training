# Scenario

The proxy publishes a service over HTTPS, talks to its backend over TLS, and
everything answers. **That is exactly the problem.**

Four things are wrong, and none of them produces an error:

1. The backend is reached over TLS with verification **disabled**. The link
   is encrypted and the peer's identity is not looked at. The `/api-usurpe/`
   route demonstrates it: it leads to a backend whose certificate is signed by
   a **foreign authority** and which carries **the same name** as the
   legitimate one. It serves the same marker, so its answer is
   indistinguishable from a success.

2. No client identity is requested. The `/prive/` route is therefore public.

3. `option forwardfor` **appends** to the received header instead of replacing
   it. A client sending its own `X-Forwarded-For` has its value arrive
   **first** at the application, which almost always reads the first.

4. The listener that accepts the PROXY protocol is open to the whole network.
   A client can therefore declare whatever address it wants by another path.

The last two are the same fault seen from two sides. Closing one leaves the
other open, which is why they are placed together.

Four distinct authorities are provided, described along with the routes and
identities in `/opt/pub-haproxy-confiance/recette.txt`.

## Mission

Plug the chain of trust back in, in both directions and on both identities:
the backend's, the client's, and the source's.

## The four checks

1. **The backend's identity is verified, and the impostor refused.** This
   check is critical. The `/api-usurpe/` canary must go to **502** and stay
   there: its refusal is the proof that verification is strict, so removing it
   would remove the proof. The legitimate route must keep answering: refusing
   everything is not verifying.

2. **A valid client identity is told apart from an absence and from another
   authority.** Also critical, and measured with all three cases: no
   certificate, one from a foreign authority, and one from the clients'
   authority. The public route must stay open without identity: the recipe
   asks for route authorisation, not a gate.

3. **A client cannot choose its own address.** Critical, and measured from
   both sides: a header sent by the client must not reach the application, and
   the listener that trusts the PROXY protocol must not be reachable from the
   network.

   The half that matters is the third measurement: from the approved source, a
   declared address **must** reach the application. Without it, the check
   would be satisfied by deleting the listener, and the configuration would
   have lost a capability instead of gaining a control.

4. **The authorised route preserves protocol and identity up to the
   application.** The backend returns what it received, and the test reads its
   values: the original protocol, the client's address, and the name carried
   by the client certificate. Without that echo, the proxy would have to be
   taken at its word.
