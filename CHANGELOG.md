# Changelog

All notable changes to this catalog are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this catalog
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**What a version means here.** A catalog is not a library: a MINOR bump adds
labs, a PATCH fixes a statement or a test without changing what a lab proves,
and a MAJOR renames or removes labs, which breaks the progress already recorded
by learners.

## [1.0.0] - 2026-10-26

### Added on 2026-10-26

- **The whole Nginx track, ten labs**, and **the whole HAProxy track, eleven
  labs**. Both series run from installation to troubleshooting and updating,
  and each ends with a lab that reboots the machine: a service that answers
  today and does not come back tomorrow is not installed, it was started.

  Every lab carries its encrypted reference solution, four bilingual hints at
  increasing cost, and tests that measure the state of the system rather than
  the commands typed. **None of the twenty-one is attested**, and that is
  written here rather than left to be discovered: they were exercised by
  review and by running their components in isolation, not end to end on a
  VM.

- **A second entry machine, `edge2.lab`**, appended to `infra.hosts`. It
  serves only `pub-haproxy-ha`: proving a failure domain takes two machines,
  and one only proves the loss of a process. Since the `infra:` contract is
  shared by the repository, every lab now starts three VMs instead of two,
  that is 7 GB of memory instead of 5.

### Fixed on 2026-10-26

- **`pub-nginx-tls` claimed that a global redirect to HTTPS prevents an
  HTTP-01 challenge from validating.** That is too strong: Let's Encrypt's
  validator follows redirects, up to ten, towards ports 80 and 443, and does
  not verify the target's certificate. The text now states what stays true
  whatever the authority: a redirect puts the challenge outside the control
  of whoever writes it, it fails on the first issuance since nothing listens
  on 443 yet, and it breaks as soon as the target leaves the two allowed
  ports.

- **`pub-nginx-tls` shipped an unplayable reference solution.** It used
  `http2 on;`, a form that only exists from Nginx 1.25.1, while the labs run
  on Ubuntu 24.04's package, that is 1.24. An unknown directive is not
  ignored: it makes `nginx -t` fail, and with it the whole file.

### Added on 2026-10-25

- **Two labs the published pages already cited and that did not exist**:
  `pub-haproxy-protection` and `pub-nginx-observation`. A reader following
  `nginx-proteger-observer` or `haproxy-proteger-observer` was sent to an
  exercise that was not there. Both come with a Vault-encrypted reference
  solution and four cost-tiered bilingual hints; neither is attested yet, and
  the CHANGELOG says so rather than leaving it to be discovered.

  `pub-haproxy-protection` is built on what HAProxy does and the Nginx lab
  does not cover: a per-source rate limit with a `stick-table`. Its central
  test proves three things at once, because no single one is enough: a burst
  of 40 requests must meet both 429s and 200s (only 429s would be a closed
  door, only 200s no limit at all), and the service must come back once the
  window has passed, because a rate limit releases.

  `pub-nginx-observation` rests on one idea: observing is not writing fields.
  A log where `request_time` always read `0.000` would be structured,
  parsable and useless. The backend therefore serves a page that sleeps two
  seconds and one that answers 503, and the tests confront the logged value
  with those facts.

- **Hints for the four option labs that had none** (`pub-nginx-publication`,
  `pub-nginx-protection`, `pub-haproxy-tls`, `pub-haproxy-observabilite`), and
  the seven missing `lab.fr.yaml`. The two timed assessments keep no hints:
  their scenarios state that none is provided, so their absence is a rule of
  the lab, not an oversight.

- **`scripts/chiffrer-solutions.sh`**, which the sibling catalogs all had. The
  reference solutions existed only encrypted here, so reading one meant an
  `ansible-vault view` by hand and changing one meant a round trip nothing
  guided. A solution whose cleartext has not changed is not re-encrypted: the
  ciphertext changes on every pass, and recomputing it for nothing would make
  the lab look modified and its attestation stale.

- **A `ruff` pre-commit hook.** The `[tool.ruff]` section had been in the
  pyproject from the start, but no hook ever called it: eleven errors were
  asleep in four labs, including a `zip()` without `strict=` and a variable
  named `l`. A configuration nothing runs is not a rule, it is an intention.
  All eleven are fixed.

### Fixed on 2026-10-25

- **`pub-traefik-mtls` concluded on "any status other than 200".** Measured by
  counter-test: that criterion takes **seven situations out of ten** for a TLS
  refusal, among them a service that is down, an unreadable certificate file
  and a 404 from routing. With the invalid backend answering 404, the backend
  test passed green having demonstrated no refusal at all. The tests now read
  curl's exit code as well, which separates what the HTTP code conflates, and
  `tests/test_discriminant_mtls.py` replays the ten situations on every
  commit.

- **`pub-epreuve-socle` graded two things it could not judge.** The
  architecture dossier was scored on a 200-character threshold and a handful
  of expected words: incoherent text long enough and sprinkled with "tls",
  "certificat" and "responsab" passed the assessment. And the incident
  diagnosis looked for its keyword in `composant` AND `explication` combined,
  so the structured field could stay empty while free prose earned the point,
  while a learner who properly wrote down the hypotheses they had **ruled
  out** was failed by the "naming every layer at once is not a diagnosis"
  check. Grading now rests on the structured fields compared against the
  secret; the prose is required to be present and declared ungraded, and both
  scenarios announce the split.

- **`pub-socle-exposition` classed a reachable service as closed.** Its probe
  read the response body, so a service answering **204 No Content** was
  reported as a closed port. It now reads `%{http_code}`.

### Known gaps

- `pub-haproxy-protection` and `pub-nginx-observation` carry no entry in
  `validation-labs.json`: attesting them needs the lab machines and a
  dedicated campaign. The three labs fixed above, and the four whose tests
  were touched by the lint pass, must be replayed for the same reason.

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
- TLS clients in the tests now explicitly require TLS 1.2 as their minimum;
  the tests still verify that the server rejects TLS 1.0 and 1.1.

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
