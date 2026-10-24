# Challenge: throttle and observe the Nginx proxy

## Criteria

- A burst of requests from one client receives `429` for some of them, while a
  single request after the burst still receives `200`.
- `/opt/pub-nginx-observation/logs/access.log` contains one JSON object per
  line with `time`, `remote_addr`, `request_uri`, `status` and `request_time`.
- `stub_status` answers on `127.0.0.1:8081` and the port is not reachable from
  the network.
- The application is still published on port 80.

The reference solution is not included in the guides.
