# Changelog

All notable changes to this catalog are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this catalog
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**What a version means here.** A catalog is not a library: a MINOR bump adds
labs, a PATCH fixes a statement or a test without changing what a lab proves,
and a MAJOR renames or removes labs, which breaks the progress already recorded
by learners.

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

- The `doc_url` of `pub-01-acme-pebble` pointed at
  `/docs/services/web/certificats-acme/`, which answers **404**: that page does
  not exist, and the lab's README still announced a guide "being written". It
  now points at `/docs/services/reseau/traefik-tls-acme/`, which answers 200
  and teaches the subject. A first attempt pointed at the section pivot, which
  was a rule error: a lab attaches to the page that covers the skill, never to
  a pivot.

### Known gaps

- `pub-02-traefik-docker` carries a **ROUGE** verdict: the reference solution
  passes 5 tests out of 6. Either it is wrong, or a test demands the
  impossible. It is recorded as ROUGE rather than hidden, and it is the next
  thing to settle here.
