# Changelog

All notable changes to this catalog are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this catalog
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**What a version means here.** A catalog is not a library: a MINOR bump adds
labs, a PATCH fixes a statement or a test without changing what a lab proves,
and a MAJOR renames or removes labs, which breaks the progress already recorded
by learners.

## [1.0.0] - 2026-10-24

### Added

- Labs proving ACME renewal at the HTTPS endpoint, authenticated HTTPS access
  to Traefik administration with a restricted Docker socket proxy, security
  headers, and rate limiting, and service recovery after a Docker daemon
  restart. Their reference solutions are encrypted with `ansible-vault`.
- A systemd backend routed through Traefik's file provider, with a measured
  dynamic configuration reload and no proxy restart.
- A middleware challenge that measures path rewriting, permanent redirects,
  security headers, and gzip compression. Its Vault-encrypted reference
  solution passes all five checks; the initial state scores 0/100.
- An observability challenge that verifies filtered JSON access logs, a live
  Traefik target in Prometheus, and a 5xx alert fired by a real HTTP 503
  response. Its Vault-encrypted solution passes all four tests after the
  initial state scores 0/100.
- A troubleshooting challenge for five live Traefik failures, validated at
  0/100 before and 100/100 after its Vault-encrypted reference solution.
- A Traefik upgrade challenge from v3.7.6 to v3.7.15, with pinned image
  digests, a live configuration check, and an executed rollback-and-recovery
  proof. Its reference solution is encrypted with `ansible-vault`.
- A timed, no-hint first-level assessment that tests two external HTTPS
  services, Pebble certificate renewal, blocked backend and administration
  ports, and recovery after a Docker daemon restart.
- A timed, no-hint level-two assessment that protects administration, verifies
  rate limiting and security headers, observes real 5xx responses in JSON
  logs and Prometheus, and requires a written diagnosis of an injected outage.
- An optional HAProxy 3.4 lab that uses its experimental native ACME client to
  issue and renew a certificate from Pebble without restarting the proxy; the
  Vault-encrypted solution passes all four tests from a 0/100 baseline.
- An optional HAProxy observability lab that publishes private Prometheus
  metrics, verifies the scrape and backend health, and restricts both
  monitoring ports to loopback. Its Vault-encrypted solution passes 4/4 tests
  from a 0/100 baseline.
- Two optional Nginx labs: reverse-proxy publication with forwarding headers,
  and proxy hardening with security headers, authenticated administration,
  dotfile denial, and method restrictions. Both reference solutions are
  Vault-encrypted; the labs pass 1/1 and 4/4 tests from 0/100 baselines.

### Fixed

- The canonical `pub-traefik-protection` lab now measures eight checks:
  the vulnerable baseline scores 0/100 and its encrypted reference solution
  passes 8/8 checks.
- The redirect-loop check resolves both HTTP and HTTPS to the local Traefik
  instance while following redirects, so it tests proxy behavior rather than
  external DNS.
- The `pub-traefik-docker` stopped-instance check allows at most one transient
  error during detection, then requires five seconds with no errors or traffic
  to the stopped instance. Replayed on 2026-10-24: 0/100 before, 100/100 after,
  all 6 tests passing.

## [0.1.0] - 2026-10-23

### Added

- **First publication.** Two labs to publish services behind a reverse proxy
  with automatic certificates, 1 h 10 in all, on one Ubuntu 24.04 machine.

- The two reference solutions are encrypted with `ansible-vault`.

- **The contribution chain of the sibling catalogs**: Zizmor, Actionlint,
  Poutine, pre-commit parity and CodeQL on `python` and `actions`, plus
  Plumber, Scorecard, Dependabot and the issue templates. The CI goes from one
  job to **six**, for seven required checks, and `main` carries the same
  ruleset as the others: linear history, pull request with one review, and the
  seven checks.

- The hook that refuses a verdict committed together with what it measures,
  and the `ruff` rule set shared by the collection.

### Fixed

- The `doc_url` of the Pebble ACME lab pointed at
  `/docs/services/web/certificats-acme/`, which answers **404**: that page does
  not exist, and the lab's README still announced a guide "being written". It
  now points at `/docs/services/reseau/traefik-tls-acme/`, which answers 200
  and teaches the subject. A first attempt pointed at the section pivot, which
  was a rule error: a lab attaches to the page that covers the skill, never to
  a pivot.

### Known gaps

- The Traefik Docker lab initially carried a **ROUGE** verdict: the reference
  solution passed 5 tests out of 6. It was subsequently repaired and validated.
