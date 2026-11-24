# Publish an application with Nginx

## The situation

A small application is running on the VM, but Nginx does not publish it yet.
The supplied container and configuration are ready for you to complete.

## Mission

Configure Nginx to reverse-proxy `app.lab.test` to the local application.
Preserve the request path and host, and send the forwarding headers expected
by an application behind a proxy.

## What is asked

### Criteria

- Requests for `app.lab.test` reach the local application through Nginx.
- The request path and `Host` header are preserved.
- Nginx supplies the `X-Forwarded-For` and `X-Forwarded-Proto` headers.

The reference solution is not included in the guides.
