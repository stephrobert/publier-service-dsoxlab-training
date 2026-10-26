# pub-haproxy-ha

Two entry points serve the same service with the same certificate, and
nothing makes them one. Deploy the failover, then lose a process and a
host while the client keeps asking the same address.

```bash
dsoxlab run pub-haproxy-ha
dsoxlab check pub-haproxy-ha
```
