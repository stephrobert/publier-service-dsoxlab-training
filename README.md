# publier-service-dsoxlab-training

**Language:** [English](./README.md) · [Français](./README.fr.md)

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
dsoxlab run       pub-01-acme-pebble
dsoxlab challenge pub-01-acme-pebble
dsoxlab check     pub-01-acme-pebble
dsoxlab clean     pub-01-acme-pebble   # undoes the lab, keeps the machine
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

| Lab (id) | Title | Type | Companion guide |
|---|---|---|---|
| `pub-01-acme-pebble` | Obtain a certificate automatically with ACME | lab | guide being written (in French) |

## Contributing

Read [`CONTRIBUTING.md`](./CONTRIBUTING.md). In short: a lab is proven **in both
directions** before it is merged, `dsoxlab validate-structure` is green, and the
statement exists in English and in French.

Anything user-facing is bilingual. A document translated on one side only is
reported by the validator, not left to goodwill.

## License

See [`LICENSE`](./LICENSE).
