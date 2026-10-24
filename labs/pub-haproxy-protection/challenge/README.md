# Challenge: protect the HAProxy frontend

## Criteria

- `/admin` answers `200` from `127.0.0.1` and `403` from the network address
  of the VM.
- Every response carries `X-Content-Type-Options: nosniff` and
  `X-Frame-Options: DENY`.
- A client that exceeds 20 requests in 10 seconds receives `429`.
- Ordinary requests to the application keep answering `200`.

The reference solution is not included in the guides.
