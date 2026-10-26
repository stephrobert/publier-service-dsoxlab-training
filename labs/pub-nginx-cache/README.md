# pub-nginx-cache

A catalogue is cached behind Nginx, and cached wrongly: the origin's
`Cache-Control` is ignored, the key sees neither the language nor the
session, and an `X-Cache-Status: HIT` header is added to every
response. Apply the content contract instead.

```bash
dsoxlab run pub-nginx-cache
dsoxlab check pub-nginx-cache
```
