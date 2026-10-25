# The task

On `edge.lab`, edit `/etc/pub-app/politique.yaml` (re-read on every
request, no restart needed) so that all four points below hold. Nothing
else needs to be written: the tests observe the application and the entry
point directly, with the automated browser already installed there.

```yaml
entete_proto:
  transmettre: <true|false: does the entry point tell the application it
    really terminated HTTPS, instead of letting the application assume it
    never does?>
cookie:
  domaine: <the Domain attribute of the session cookie: a literal string
    a browser will actually accept for this host, or empty to let the
    browser default it correctly>
cors:
  autoriser_toutes_origines: <true|false: does the policy say yes to any
    origin, instead of checking it against the one partner origin it
    actually trusts?>
  origine_autorisee: <left as provided, do not change it>
identite:
  faire_confiance_entete_client: <true|false: does the entry point repeat
    whatever identity header the client already sent, instead of deciding
    it from the session cookie it has actually validated?>
```

Read `/home/student/README-app` for the exact ports in this run. Use the
automated browser to check your own work before relying on the tests:

```sh
sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
  python3 /opt/pub-app/verifier_navigateur.py parcours <port_entree>
sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
  python3 /opt/pub-app/verifier_navigateur.py cors <port_partenaire> <port_intrus>
sudo -u student env PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
  python3 /opt/pub-app/verifier_navigateur.py identite <port_entree>
```

The tests run the same three checks themselves, from `edge.lab`, and
never trust a response header alone when the point being tested is
something only a real browser enforces.
