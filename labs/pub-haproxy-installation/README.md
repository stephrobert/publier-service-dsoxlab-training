# pub-haproxy-installation

HAProxy is installed and stopped, with a configuration that carries no
listener at all. Publish what the manifest describes, then show that an HTTP
frontend and a TCP relay are not the same thing: one understands requests, the
other only moves bytes.

```bash
dsoxlab run pub-haproxy-installation
dsoxlab check pub-haproxy-installation
```
