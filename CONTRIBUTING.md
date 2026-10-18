# Contributing

## The one rule

**A lab is graded on the state of the system, never on the commands typed.**

A test that reads back what the learner wrote proves nothing: they could have
written it without understanding it, and they could have reached the same state
by another path that the test would wrongly reject.

```python
# NO: we re-read what the learner wrote
assert "myoption" in config_text

# YES: we ask the system what it actually does
assert service.is_running and service.is_enabled
```

## A lab is proven in both directions

Before a lab is merged:

1. `dsoxlab run <id>` then `dsoxlab check <id>` must score **0**. A test that
   is green before the work is not a test, it is an assumption about the setup.
2. With the reference solution in place, `dsoxlab check <id>` must score
   **100**.
3. `dsoxlab clean <id>` must give the machine back as it was. A lab that leaves
   something behind is not that lab's problem, it is the next lab's.

## Everything user-facing is bilingual

The statement exists in English and in French: `README.md` and `README.fr.md`,
`scenario.md` and `scenario.fr.md`, `lab.yaml` and `lab.fr.yaml`.

Assertion messages are a special case: the contract imposes a single file name,
`challenge/tests/test_functional.py`, so there is no English version by
duplication. Use the `message(en=…, fr=…)` helper of `conftest.py`.

## Before opening a pull request

```bash
dsoxlab validate-structure     # the contract, offline
pytest tests/                  # this repository's own guardrails
dsoxlab list-labs              # FIRST: a lab.yaml that raises disappears here
```

Run `list-labs` **before** `validate-structure`: the validator iterates over
the labs already loaded, so a lab whose `lab.yaml` raises passes validation
without a word.
