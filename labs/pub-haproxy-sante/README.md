# pub-haproxy-sante

HAProxy runs with two servers at equal weights and nobody watching them: a
backend that falls stays in the rotation, and one request in two goes to it.
The thresholds are prescribed, because the validation measures windows, not
intentions.

```bash
dsoxlab run pub-haproxy-sante
dsoxlab check pub-haproxy-sante
```
