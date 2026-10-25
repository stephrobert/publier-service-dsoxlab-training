# pub-haproxy-tls

Use HAProxy 3.4's experimental native ACME client to publish a TLS service
with a Pebble-issued certificate, then renew it without restarting HAProxy.

```bash
dsoxlab run pub-haproxy-tls
dsoxlab check pub-haproxy-tls
```
