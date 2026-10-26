# pub-haproxy-tls-stable

The application is published in HTTP and nothing more: no certificate, no
`bind ssl`, no route for the ACME challenge. A test authority and an external
ACME client are provided. The validation runs your renewal script rather than
inspecting its result, because a cycle is not observed afterwards.

```bash
dsoxlab run pub-haproxy-tls-stable
dsoxlab check pub-haproxy-tls-stable
```
