# Scenario

Two generations of the application are installed. **1.4.2** is in service,
**1.5.0** is available and stopped. Nothing moves from one to the other:
that is what you deliver.

The plan is in `/opt/pub-haproxy-mise-a-jour/plan.txt`, the generations and
paths in `manifeste.txt`.

## What this lab measures and the others do not

**The master and its workers.** A HAProxy reload does not replace the master
process: it makes it start **new** workers, and leaves the **old** ones
alive until the connections they hold finish. Both generations of workers
therefore coexist for a few minutes.

That is exactly what makes a reload without an outage possible, and it is
also what imposes a rule the plan states: **a delivery does not remove the
generation it replaces.** The old workers are still talking to it. It
removes the one that was replaced at the previous delivery.

The master holds the listening sockets. Replacing it closes the port, and no
client-side measurement catches a second during which nothing listens. The
test therefore compares its PID before and after.

## The five checks

1. **The starting state**, and both `livrer` and `revenir` executables
   present and executable.

2. **The delivery brings the plan's version without cutting.** The
   validation opens a long flow, starts a continuous probe, **runs your
   `livrer 1.5.0`**, and measures during the switch: at most one failed
   short request, the long flow still receiving and reaching its end, the
   master's PID unchanged, and new workers appeared.

3. **The rollback restores the generation**, with the same availability
   requirement. Critical check.

4. **The journal says what was measured.** Read by a human.

5. **Everything comes back after a reboot.** Critical, and last since it
   cuts the machine.
