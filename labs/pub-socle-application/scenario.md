# Scenario

A small application was deployed behind a TLS entry point on `edge.lab`,
everything running on `127.0.0.1` (the automated browser runs on the same
host). The configuration shipped with four mistakes at once: the login
journey redirects forever instead of landing on the account page, the
session cookie is scoped to a domain no browser will ever accept, the
cross-origin policy says yes to any origin, and the entry point still
repeats whatever identity header the client sends instead of deciding it
from a validated session.

## Mission

Read `/home/student/README-app`, then edit `/etc/pub-app/politique.yaml`
(re-read on every request, no restart needed) so that:

- the login journey ends on the HTTPS account page without looping;
- the legitimate session, once used in the browser, shows the account as
  connected;
- the partner origin can read the API response, the intruder origin
  cannot, both checked from a real browser;
- a forged identity header sent directly by the client never grants
  access to the account.

Use the provided automated browser, `/opt/pub-app/verifier_navigateur.py`,
to observe each of these from where they actually happen, a real browser
engine, not just response headers.
