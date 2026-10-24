# Scenario

A small application is available on the host, but the supplied HAProxy
deployment does not provide HTTPS correctly. The test ACME authority Pebble
and its HTTP-01 challenge responder are prepared for you.

## Mission

Configure HAProxy 3.4 to route `app.lab.test` to the local backend, redirect
HTTP to HTTPS, and obtain the certificate through HAProxy's native ACME client.
Keep the ACME account key private and prove that a renewed certificate is
served while the proxy process remains running.

Native ACME support is experimental in HAProxy 3.4 and requires
`expose-experimental-directives`. The reference solution is not included in
the guides.
