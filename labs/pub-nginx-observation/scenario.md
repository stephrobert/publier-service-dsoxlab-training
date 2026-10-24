# Scenario

Nginx already publishes the application, but a single client can flood it with
requests, the access log is plain text that nobody can filter, and there is no
way to read the proxy's connection counters.

## Mission

Limit the request rate per client address so that a burst is answered with
`429` while a normal request still gets `200`. Write the access log as one
JSON object per line in `/opt/pub-nginx-observation/logs/access.log`, with the
fields `time`, `remote_addr`, `request_uri`, `status` and `request_time`.
Expose `stub_status` on `127.0.0.1:8081` only, without opening that port to
the network.
