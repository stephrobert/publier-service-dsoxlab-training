# pub-socle-tls

**Audience:** the learner.

Learn to decide whether a TLS endpoint really proves the identity it claims,
using an explicitly provided trust store rather than skipping verification.

## What you will be able to do

- Verify a certificate chain against a given root of trust instead of trusting
  whatever is presented.
- Tell a wrong name, a broken chain and an expired certificate apart by their
  actual verification failure, not by guessing.
- Decide, from the observed state alone, whether an endpoint should be
  accepted or refused.

Your work happens on `edge.lab`; `challenge/README.md` describes the file to
produce.
