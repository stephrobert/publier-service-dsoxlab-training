# pub-haproxy-confiance

Four authorities, two backends carrying the same name, and a HAProxy where
everything answers. That is the point: the four faults in place produce no
visible error. A chain of trust that is entirely unplugged looks exactly like
one that works.

```bash
dsoxlab run pub-haproxy-confiance
dsoxlab check pub-haproxy-confiance
```
