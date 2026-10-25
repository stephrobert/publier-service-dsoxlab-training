# pub-socle-reverse-proxy

**Audience:** the learner.

Learn to read a chain of two reverse proxies as two separate trust
decisions: who is allowed to say where a request really came from, and who
is allowed to say which identity it carries. A reverse proxy chain is only
as trustworthy as the narrowest point where an untrusted client still gets
to speak: if any hop downstream still believes whatever the hop before it
claims, a forged header travels all the way to the application unchanged.

## What you will be able to do

- Tell which hop of a proxy chain terminates TLS and which ones relay in
  plain HTTP, and check it against the real traffic rather than assume it.
- Explain why a legitimate client's origin and identity must be decided by
  the proxy that is actually in contact with it, not merely repeated by
  every hop that follows.
- Show that a forged `X-Forwarded-For` or identity header, injected from an
  untrusted client, grants no privilege once the chain is fixed.
- Close the direct paths that let a client reach an internal hop or the
  application while bypassing the chain entirely.

Your observations happen from `poste.lab` and `edge.lab`; the deliverable is
written on `edge.lab`. `challenge/README.md` describes it precisely.
