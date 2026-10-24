# Configure HTTPS and ACME in Traefik

You administer `edge.lab`. The `app.lab.test` service must be available over
HTTPS behind Traefik. A test ACME authority is already running on the machine
and issues short-lived certificates so renewal can be observed during a lab.

## Mission

Configure Traefik to obtain and renew the ACME certificate for `app.lab.test`
automatically, without manual intervention after startup. HTTP requests must
redirect to HTTPS, the ACME storage must be protected, and obsolete TLS
protocol versions must be rejected.

The proof is not limited to a certificate in storage: the storage file must
have restrictive permissions, the authority's log must show at least two
distinct issuances, and an HTTPS client must receive the renewed certificate,
valid for the expected name and issued by this session's authority.

`/opt/pub-traefik-acme/LISEZ-MOI.txt` describes the available services and
constraints on the machine.
