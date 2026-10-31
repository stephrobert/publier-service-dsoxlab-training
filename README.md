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
- **A hypervisor**, because every lab here is `runtime: vm`:
  **libvirt/KVM** (with `terraform` and the `dmacvicar/libvirt` provider) is
  the default provider declared in [`meta.yml`](./meta.yml). To use Incus
  instead, change `infra.provider: kvm` to `infra.provider: incus` before
  provisioning.
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

<!-- LABS:START -->
### Foundations: understand and diagnose a published service

Identify the service behind a web response, read an HTTP exchange, switch a DNS record safely, and obtain a certificate automatically with ACME.

| Lab (id) | Title | Level | Runtime | Companion guide |
|---|---|---|---|---|
| `pub-socle-service` | Identify the service behind a web response | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/service-web-publier/) |
| `pub-socle-http` | Read and explain an HTTP exchange | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/http-lire-echange/) |
| `pub-socle-dns` | Diagnose and switch a DNS record safely | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/dns-preparer-bascule/) |
| `pub-acme-pebble` | Obtain a certificate automatically with ACME | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/certificats-acme/) |
| `pub-socle-exposition` | Close the paths that bypass the entry point | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/exposition-ports-pare-feu/) |
| `pub-socle-dns-http-tls` | Separate the resolved name, the certificate and the HTTP route | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/publier-un-service/) |
| `pub-socle-reverse-proxy` | Define the responsibilities and the trust of a proxy chain | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/reverse-proxy/) |
| `pub-socle-tls` | Check a TLS identity and its chain of trust | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/reseaux/fondamentaux/tls-diagnostic/) |
| `pub-socle-application` | Fix a session, its cookie, and its origins behind a proxy | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/application-derriere-proxy/) |
| `pub-socle-flux-longs` | Observe a WebSocket and an event stream | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/flux-longs-protocoles/) |
| `pub-socle-disponibilite` | Measure a backend outage, removal and return | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/equilibrer-sante-service/) |
| `pub-socle-observabilite` | Define an SLI and an alert seen from the client | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/observer-service-publie/) |
| `pub-socle-mise-en-service` | Hand over a release and prove it can be restored | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/mise-en-service-reprise/) |
| `pub-socle-depannage` | Diagnose a publication, layer by layer | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/diagnostiquer-par-couches/) |
| `pub-socle-securite` | Write and test a web service access policy | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/securite-point-entree/) |
| `pub-socle-cache-delais` | Measure the effects of a cache and of retries | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/delais-tentatives-cache/) |
| `pub-epreuve-socle` | Socle assessment: design and hand over a service | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/epreuve-socle/) |

### Traefik: publish, protect and operate a reverse proxy

Publish containers and host services behind Traefik, secure, observe, diagnose and upgrade the entry point, then prove it in the two level assessments.

| Lab (id) | Title | Level | Runtime | Companion guide |
|---|---|---|---|---|
| `pub-traefik-modele` | Trace a request through Traefik's routing model | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik/) |
| `pub-traefik-installation` | Install Traefik and master its entry-point lifecycle | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-installation/) |
| `pub-traefik-docker` | Publish two containers behind Traefik, with the Docker provider | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-docker/) |
| `pub-traefik-fichier` | Publish a systemd service with Traefik's file provider | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-fichier/) |
| `pub-traefik-routage` | Resolve routing priorities and collisions | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-routage/) |
| `pub-traefik-acme` | Configure HTTPS, ACME renewal, and modern TLS in Traefik | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-tls-acme/) |
| `pub-traefik-restart-recovery` | Keep a containerized web service available after a Docker restart | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-installation/) |
| `pub-epreuve-niveau-un` | Level 1 assessment: publish and recover services | niveau-1 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/epreuve-niveau-1/) |
| `pub-traefik-middlewares` | Compose and verify Traefik middlewares | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-middlewares/) |
| `pub-traefik-protection` | Protect the Traefik entry point | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-securite/) |
| `pub-traefik-mtls` | Verify backend TLS and client certificates | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-mtls/) |
| `pub-traefik-flux-delais` | Bound delays and keep long-lived flows alive | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-flux-delais/) |
| `pub-traefik-observabilite` | Observe Traefik with JSON access logs and Prometheus | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-observability/) |
| `pub-traefik-depannage` | Troubleshoot Traefik routing and TLS failures | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-depanner/) |
| `pub-traefik-mise-a-jour` | Upgrade Traefik and prove a rollback | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-upgrade/) |
| `pub-epreuve-niveau-deux` | Level 2 assessment: protect, observe, and diagnose | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/epreuve-niveau-deux/) |
| `pub-traefik-zero-downtime` | Roll out a backend version, prove rollback, and name the real failure domain | niveau-2 | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/traefik-disponibilite/) |

### HAProxy: publish and operate web services

Publish HTTPS with HAProxy native ACME and observe it with Prometheus.

| Lab (id) | Title | Level | Runtime | Companion guide |
|---|---|---|---|---|
| `pub-haproxy-tls` | Publish HTTPS with HAProxy native ACME | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-tls-acme/) |
| `pub-haproxy-protection` | Protect an application with HAProxy | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-proteger-observer/) |
| `pub-haproxy-observabilite` | Observe HAProxy with Prometheus | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-proteger-observer/) |
| `pub-haproxy-installation` | Install HAProxy and tell its HTTP and TCP modes apart | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-installer/) |
| `pub-haproxy-routage` | Route with ACLs and a map, without a leaking default | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-routage/) |
| `pub-haproxy-sante` | Probe, remove and drain backends | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-sante/) |
| `pub-haproxy-tls-stable` | Publish TLS with a certificate cycle you have exercised | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-tls-stable/) |
| `pub-haproxy-confiance` | Check the identity of the backend and of the source | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-confiance/) |
| `pub-haproxy-stick-tables` | Limit by a key you control, and read the counters | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-stick-tables/) |
| `pub-haproxy-flux-delais` | Bound time, queues and long streams | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-flux-delais/) |
| `pub-haproxy-runtime` | Change the runtime state with limited rights | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-runtime/) |
| `pub-haproxy-depannage` | Diagnose an unknown HAProxy outage | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-depanner/) |
| `pub-haproxy-mise-a-jour` | Reload, update and roll back HAProxy | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-mise-a-jour/) |
| `pub-haproxy-ha` | Prove the failure domain of two entry points | option-haproxy | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/reseau/haproxy-disponibilite/) |

### Nginx: publish and protect web services

Publish an application with Nginx and protect it.

| Lab (id) | Title | Level | Runtime | Companion guide |
|---|---|---|---|---|
| `pub-nginx-publication` | Publish an application with Nginx | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-publier/) |
| `pub-nginx-installation` | Install Nginx and master validation and reload | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-installer/) |
| `pub-nginx-routage` | Verify server and location selection | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-routage/) |
| `pub-nginx-statique` | Serve only the files you intended | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-statique/) |
| `pub-nginx-upstream` | Measure load sharing and passive detection | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-upstreams/) |
| `pub-nginx-tls` | Renew and serve an Nginx certificate | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-tls/) |
| `pub-nginx-limites` | Limit abuse while keeping legitimate clients | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-limites/) |
| `pub-nginx-flux-longs` | Publish WebSocket, SSE and gRPC with Nginx | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-flux-longs/) |
| `pub-nginx-cache` | Cache public responses without sharing private data | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-cache/) |
| `pub-nginx-depannage` | Diagnose and repair Nginx | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-depanner/) |
| `pub-nginx-mise-a-jour` | Upgrade, roll back and reboot Nginx | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-mise-a-jour/) |
| `pub-nginx-protection` | Protect an application with Nginx | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-proteger-observer/) |
| `pub-nginx-observation` | Observe an Nginx reverse proxy | option-nginx | vm | [guide (FR)](https://www.stephane-robert.info/docs/services/web/nginx-observer/) |

_61 labs, table generated by `scripts/gen_catalog.py`._
<!-- LABS:END -->

### Alignment with the course roadmap

The original target was **11 core labs plus four optional labs**, 15 labs in
all, and they are implemented and validated. The course contract
(`publier-service`, v2) now plans 67 labs: the catalog above holds the 36
written so far, each validated 0 to 100 (`validation-labs.json`). The Nginx
and HAProxy sections are still short and keep growing.

## Contributing

Read [`CONTRIBUTING.md`](./CONTRIBUTING.md). In short: a lab is proven **in both
directions** before it is merged, `dsoxlab validate-structure` is green, and the
statement exists in English and in French.

Anything user-facing is bilingual. A document translated on one side only is
reported by the validator, not left to goodwill.

## License

See [`LICENSE`](./LICENSE).
