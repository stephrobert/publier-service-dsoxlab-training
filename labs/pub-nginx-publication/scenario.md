# Scenario

A small application is running on the VM, but Nginx does not publish it yet.
The supplied container and configuration are ready for you to complete.

## Mission

Configure Nginx to reverse-proxy `app.lab.test` to the local application.
Preserve the request path and host, and send the forwarding headers expected
by an application behind a proxy.
