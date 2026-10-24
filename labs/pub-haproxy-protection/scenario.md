# Scenario

HAProxy already publishes the application, but `/admin` is reachable from any
address, one client can send unlimited requests, and the responses carry no
security header.

## Mission

Allow `/admin` only from the loopback address `127.0.0.1` and answer `403` to
every other source. Answer `429` to a client that sends more than 20 requests
in 10 seconds. Add `X-Content-Type-Options: nosniff` and
`X-Frame-Options: DENY` to every response. Ordinary requests must keep
working.
