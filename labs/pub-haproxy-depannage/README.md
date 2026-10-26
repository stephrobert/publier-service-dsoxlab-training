# pub-haproxy-depannage

A healthy stack, one injected fault among routing, probe, backend TLS, a
limit or saturation, and configuration noise that is the cause of none of
them. The tests do not know which variant was drawn: they replay the whole
acceptance list, which is what an operator does after an incident.

```bash
dsoxlab run pub-haproxy-depannage
dsoxlab check pub-haproxy-depannage
```
