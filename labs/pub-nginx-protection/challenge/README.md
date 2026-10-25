# Challenge: harden the Nginx application proxy

## Criteria

- Responses include `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and a restrictive Content Security Policy.
- `/admin` requires authentication and still serves the backend to an
  authenticated user.
- Dotfiles are denied.
- `DELETE` is rejected while normal application requests continue to work.

The reference solution is not included in the guides.
