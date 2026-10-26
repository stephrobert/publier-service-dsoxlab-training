# pub-haproxy-runtime

One socket, in admin mode, world-writable, and no state file. Any account on
the machine can take a server out of service, and the next reload forgets
every decision taken at runtime. Nothing is broken, and that is why nobody
looks.

```bash
dsoxlab run pub-haproxy-runtime
dsoxlab check pub-haproxy-runtime
```
