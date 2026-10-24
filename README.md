# Publish a Web Service Training: a reverse proxy, and certificates that renew themselves

**Language:** [English](./README.md) · [Français](./README.fr.md)

[![CI](https://github.com/stephrobert/publier-service-dsoxlab-training/actions/workflows/ci.yml/badge.svg)](https://github.com/stephrobert/publier-service-dsoxlab-training/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://img.shields.io/ossf-scorecard/github.com/stephrobert/publier-service-dsoxlab-training?label=OpenSSF%20Scorecard)](https://securityscorecards.dev/viewer/?uri=github.com/stephrobert/publier-service-dsoxlab-training)
[![Plumber compliance](https://score.getplumber.io/github.com/stephrobert/publier-service-dsoxlab-training.svg)](https://score.getplumber.io/github.com/stephrobert/publier-service-dsoxlab-training)
[![SLSA 3](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](./LICENSE)

Verifiable labs for the blog's
["Publish a web service" course](https://www.stephane-robert.info/docs/services/web/),
played with [dsoxlab](https://github.com/stephrobert/dsoxlab).

## What it is

At the end, a learner can put a reverse proxy in front of services that are
not reachable on their own, and get a trusted certificate for it without
touching a file by hand. Not a list of topics: every lab ends on something
observable, such as a certificate the tests parse or a response the proxy
serves.

The order matters: a proxy that publishes over HTTPS needs a certificate, so
the certificate lab comes first, against a test certificate authority that
never touches the public internet.

**A lab is graded on the state of the system, never on the commands typed.**
Learners reach the result by whatever path they choose.

## Requirements

- **Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)**
- **`git`**
- **`dsoxlab`**, the engine, installed as a standalone tool (see below).
- **A hypervisor**, because every lab here is `runtime: vm`: either
  **libvirt/KVM** (with `terraform` and the `dmacvicar/libvirt` provider) or
  **Incus**. The provider is declared as a list in [`meta.yml`](./meta.yml),
  and **a list does not resolve on its own**: pick one with
  `dsoxlab use --provider kvm`.
- **4 GB of free RAM and 20 GB of disk** for the single machine, `edge.lab`.
- **Outbound network access** on first provision, to pull the base image and
  the container images.

One virtual machine, `edge.lab` (Ubuntu 24.04, 2 vCPU, 4 GB, 20 GB), declared
in `meta.yml` and created by `dsoxlab provision`. Docker, the proxies and the
test certificate authority all run there: nothing runs on your own machine,
and ports 80 and 443 of your host stay free.

`dsoxlab doctor` says what this repository needs and what it does not, and
tells apart a check that failed from one it could not measure.

## Install

`dsoxlab` is published on [PyPI](https://pypi.org/project/dsoxlab/). Install it
as a standalone tool, so it stays out of this repository:

```bash
# 1. The dsoxlab CLI (external tool, stays out of this repo)
uv tool install dsoxlab

# 2. This lab catalog
git clone https://github.com/stephrobert/publier-service-dsoxlab-training.git
cd publier-service-dsoxlab-training

# 3. Check the contract and the machine
dsoxlab validate-structure
dsoxlab doctor
```

### Your first lab, in five minutes

```bash
export LAB_HOME=$PWD
dsoxlab use --provider kvm       # a list of providers does not resolve on its own
dsoxlab provision                # creates edge.lab, once
dsoxlab list-labs                # the catalog, in teaching order
dsoxlab run       pub-acme-pebble
dsoxlab challenge pub-acme-pebble
dsoxlab check     pub-acme-pebble
dsoxlab clean     pub-acme-pebble   # undoes the lab, keeps the machine
```

`run` is what prepares the lab. Running `check` on a lab you never started
measures nothing, and says so rather than recording a 0.

### Keeping it up to date

```bash
uv tool upgrade dsoxlab        # the engine, published on PyPI
git -C <this repo> pull        # the catalog
```

The engine and the catalog move independently: a new `dsoxlab` never requires
re-cloning the labs, and new labs never require upgrading the tool, as long as
the contract version matches.

## How it works

### The declarative contract (two levels)

The catalog is described by data, not code, which is what keeps the `dsoxlab`
engine domain-agnostic:

- **`meta.yml`** at the root declares the repository identity and the **order**
  of the sections shown by `list-labs`;
- **`lab.yaml`** per lab declares its `skills`, `level`, `runtime` (type,
  fixtures, services), `distros`, `doc_url` and a `validation` block. A
  `lab.fr.yaml` overrides `title` and `description` in French, and nothing else.

`dsoxlab validate-structure` checks the whole contract: `meta.yml` is well
formed, every referenced lab exists with a valid `lab.yaml`, every declared
test and fixture file is really there, and every relative link in a README
leads somewhere.

### The lab lifecycle

```bash
dsoxlab list-labs              # browse the catalog
dsoxlab show      <id>         # metadata and status of one lab
dsoxlab run       <id>         # set the starting state
dsoxlab challenge <id>         # read the mission, no step-by-step
dsoxlab hint      <id>         # reveal a hint (deducted from the score)
dsoxlab check     <id>         # run the tests, compute and record the score
dsoxlab clean     <id>         # undo what the lab set up
dsoxlab progress               # per-section progress, average score
```

### Runtimes

Every lab is `vm`: the containers belong to the machine, not to the learner's
host.

| Runtime | What the lab asks for |
|---|---|
| `vm` | the `edge.lab` machine, provisioned by `dsoxlab provision`, on Ubuntu 24.04. Docker and the containers run there, started by the lab's `setup.yaml`. |

### The validation model

Validation **proves the state, it does not trust the learner**. Each lab ships
`pytest` tests under `challenge/tests/` that read what the system holds, never
what a file contains or which commands were typed.

And a lab is proven **in both directions**: the tests must fail before the work
and pass after it. A test that is green before the work is not a test, it is an
assumption about the setup.

Reference solutions live under `solution/<lab>/`, encrypted with
`ansible-vault`; the password (`.vault-pass` at the root) is never versioned.
A solution in clear text would spoil the lab, and git keeps it forever.

GitHub CI checks the contract, workflows and repository quality, but does not
provision VMs or replay labs. Its badge is therefore not pedagogical evidence:
the runtime 0 → 100 cycle is checked separately with
`python3 scripts/valider-labs.py --lab <id>` on provisioned infrastructure.

### Scoring, hints, progress

`check` records a score (tests passed out of total, minus the cost of any hints
revealed). Hints are **base64-encoded** in `challenge/hints.yaml`, so that
opening the file does not give them away, and their cost grows with their
precision. History lives in a SQLite database **local to this repository**.

A run that measured nothing is neither a pass nor a failure: if every collected
test skips, `check` records no score and says why. A score of 0 would accuse the
lab of what is missing from the machine.

## Catalog

Played in order. More labs are added as they are written and proven in both
directions.

### Level 1: publish services behind a reverse proxy

| Lab | What it proves |
|---|---|
| `pub-acme-pebble` | a certificate is issued by a test ACME authority after an HTTP-01 challenge | lab, 30 min |
| `pub-traefik-docker` | two containers are published behind Traefik, discovered through the Docker socket | lab, 40 min |
| `pub-traefik-fichier` | Traefik dynamically routes to a systemd-managed host service without restarting | lab, 30 min |
| `pub-traefik-acme` | Traefik renews and serves an ACME certificate, redirects HTTP, protects storage, and rejects TLS 1.0/1.1 | lab, 40 min |
| `pub-traefik-restart-recovery` | a containerized web service recovers after the Docker daemon restarts | lab, 30 min |
| `pub-epreuve-niveau-un` | a timed assessment of two HTTPS services, renewal, external access controls, and Docker recovery | assessment, 60 min |

### Level 2: protect and operate a reverse proxy

| Lab | What it proves |
|---|---|
| `pub-traefik-middlewares` | path rewriting, permanent redirects, security headers, compressed responses, and a no-restart update | lab, 40 min |
| `pub-traefik-protection` | authenticated HTTPS administration, a restricted Docker socket proxy, security headers, and rate limiting | lab, 45 min |
| `pub-traefik-observabilite` | filtered JSON access logs, an active Prometheus metrics target, and an alert fired by a real 5xx response | lab, 40 min |
| `pub-traefik-depannage` | diagnose and repair routing, backend, timeout, certificate, and redirect failures | lab, 45 min |
| `pub-traefik-mise-a-jour` | upgrade Traefik, verify the live configuration, and prove rollback and recovery | lab, 25 min |
| `pub-epreuve-niveau-deux` | timed assessment of a protected, observable proxy and an unknown incident | assessment, 75 min |

### Optional: HAProxy

| Lab | What it proves |
|---|---|
| `pub-haproxy-tls` | native experimental ACME issuance and renewal, TLS termination, SNI, and HTTP-to-HTTPS redirect | lab, 40 min |
| `pub-haproxy-protection` | ACL restricting the admin path, per-client rate limit with a stick-table, and security headers | lab, 35 min |
| `pub-haproxy-observabilite` | private HAProxy metrics, a healthy Prometheus scrape, and monitoring ports restricted to loopback | lab, 35 min |

### Optional: Nginx

| Lab | What it proves |
|---|---|
| `pub-nginx-publication` | reverse-proxy publication with the request host, path, and forwarding headers preserved | lab, 30 min |
| `pub-nginx-protection` | security headers, authenticated administration, dotfile denial, and restricted HTTP methods | lab, 35 min |
| `pub-nginx-observation` | per-client rate limit, JSON access logs, and a loopback-only `stub_status` | lab, 35 min |

### Alignment with the course roadmap

The target remains **11 core labs (nine lesson labs and two assessments) plus
four optional labs**, for 15 curriculum labs. All 11 core labs and all four
options are implemented and validated. The renewal exercise is integrated into
the planned ACME lab; the administration exercise now covers HTTPS
authentication, Docker socket isolation, security headers, and rate limiting.
The middleware lab also covers path rewriting, redirects, security headers,
and compression. The restart-recovery exercise is an interim, independently
playable proof whose outcome is reused in the first assessment rather than
counted as an additional core slot. All 16 runnable labs, including that
interim proof, pass the 0-to-100 validation cycle.

## Contributing

Read [`CONTRIBUTING.md`](./CONTRIBUTING.md). In short: a lab is proven **in both
directions** before it is merged, `dsoxlab validate-structure` is green, and the
statement exists in English and in French.

Anything user-facing is bilingual. A document translated on one side only is
reported by the validator, not left to goodwill.

## License

See [`LICENSE`](./LICENSE).
