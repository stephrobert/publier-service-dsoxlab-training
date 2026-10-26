# pub-haproxy-stick-tables

A stick-table is already in place. It fills up, it reads fine in
`show table`, and it protects nothing: its key is a header the client sends,
its threshold is never reached, and its window and expiry are the same
number. Everything looks like it works.

```bash
dsoxlab run pub-haproxy-stick-tables
dsoxlab check pub-haproxy-stick-tables
```
