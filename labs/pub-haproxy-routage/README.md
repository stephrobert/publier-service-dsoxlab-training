# pub-haproxy-routage

HAProxy runs, four backends are healthy, and the routing is wrong in four
ways: rule order, a prefix passing for a path, a route to something not
deployed, and a default backend that catches every unknown name. Each backend
counts the requests it serves, so a leaking route cannot hide behind a
plausible answer.

```bash
dsoxlab run pub-haproxy-routage
dsoxlab check pub-haproxy-routage
```
