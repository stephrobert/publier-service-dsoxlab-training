# Security policy

## What this repository contains

A catalog of training labs: declarative files (`meta.yml`, `lab.yaml`),
statements in Markdown, Ansible playbooks, and `pytest` tests. **It executes
nothing by itself**: labs are played by the `dsoxlab` CLI, which lives in its
own repository.

## Reporting a vulnerability

Do **not** open a public issue. Use GitHub's private vulnerability reporting on
this repository, or write to the maintainers.

Please include what you found, how to reproduce it, and what you think the
impact is. You will get an acknowledgement, and a fix or an explanation of why
it is not one.

## What counts as a vulnerability here

- **A secret committed by mistake**: a token, a private key, a vault password.
  Report it even if it looks revoked: it stays in git history.
- **A lab that runs something unexpected on the learner's machine**, beyond
  what its statement announces.
- **A reference solution readable in clear text** where it is meant to be
  encrypted: it is not a system flaw, but it destroys the exercise.

## What does not

A lab that deliberately sets up a vulnerable system is the subject being
taught, not a defect. A lab that asks the learner to weaken a configuration
does so inside its own machine, which `dsoxlab destroy` gives back.
