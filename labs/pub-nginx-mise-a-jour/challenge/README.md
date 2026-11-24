# Scenario

A service is published over TLS behind Nginx, in generation **1.4.2**. A
second generation, **1.5.0**, is already on disk. Each has its own port and
its **own certificate**, and both certificates carry the same service name:
`service.lab.test`.

The manifest is in `/opt/pub-nginx-mise-a-jour/manifeste.txt`, the plan in
`/opt/pub-nginx-mise-a-jour/plan.txt`.

## Mission

Write the two executables the plan asks for:

- `livrer <version>`, which returns once that generation is **really being
  served**, with its certificate, and which is idempotent;
- `revenir`, with no argument, which brings back the previously served
  generation, with **its** certificate.

The language is yours. And keep `journal.md`: your measurements, and what you
conclude from them.

## The validation drives; it does not observe

That is what sets this lab apart. A test that runs once, at the end, sees
only a final state: it can say nothing about a sequence, and even less about
availability during a switch, which cannot be measured afterwards.

So the validation plays **your** executables, in the plan's order, and
measures between every call. The deliverable is the delivery mechanism, not
the state of the service.

## What it measures, and where

The **version served**, from the client, and not what the disk holds nor what
a symlink points at. The three can differ, and that is the defect this lab
teaches: a generation swapped on disk without the process being replaced
leaves the old code in memory.

The **fingerprint of the published certificate**, read from the handshake.
Nothing in the service name says which generation is published: only the
fingerprint does. That is why a rollback that forgets the certificate looks
like nothing at all.

## What is verified

- the starting state really is generation 1.4.2 with its certificate, and
  both executables exist and are executable;
- after `livrer 1.5.0`, the served version and the published fingerprint are
  the ones the manifest gives to 1.5.0;
- during the switch, a continuous probe is running: **at most one** failed
  request across the series. Both generations have their own port, so they
  can run at the same time, and that is what makes zero errors reachable;
- a **long flow** opened before the switch keeps receiving afterwards. A
  delivery does not cut the previous generation; the next delivery removes
  it;
- `journal.md` exists and mentions the long flow. The machine judges its
  presence and its subject, not its quality: a check that graded an
  explanation would in fact be grading the presence of keywords;
- **critical**: `revenir` brings back 1.4.2 **and** its certificate;
- **critical**: after a reboot, the acceptance list passes with no
  intervention, and the two executables are **still there**. A delivery
  mechanism written into `/tmp`, `/run` or `/dev/shm` passes once and is
  gone the next morning.

## Hints

- `systemctl reload nginx` keeps established connections on the old workers;
  `restart` cuts them all. The difference only shows on a long flow.
- A systemd template unit (`unit@instance.service`) gives you one unit per
  generation with nothing to edit. `%i` is the instance.
- `enable` and `start` are not the same thing, and the last test is what
  tells them apart.
- `revenir` needs a memory. `/run` and `/tmp` are cleared at boot;
  `/var/lib` is not.
- `openssl s_client -connect ip:443 -servername name` shows the certificate
  actually published, and `openssl x509 -noout -fingerprint -sha256` gives
  its fingerprint.
