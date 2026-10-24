# pub-haproxy-observabilite

Expose HAProxy's Prometheus metrics on a loopback-only listener, scrape the
metrics with Prometheus, and verify that the backend is healthy.

```bash
dsoxlab run pub-haproxy-observabilite
dsoxlab check pub-haproxy-observabilite
```
