# pub-epreuve-haproxy

**Audience:** the learner.

This is the HAProxy module's final assessment. HAProxy is installed and has no
mission; two services run behind it, started in a hurry; a second HAProxy
instance, `archives`, carries an unannounced fault. You are given a business
need and a recipe, never a configuration to copy.

```bash
dsoxlab run pub-epreuve-haproxy
dsoxlab challenge pub-epreuve-haproxy
dsoxlab check pub-epreuve-haproxy
```

The assessment is meant for the end of the module: it requires only what the
HAProxy lessons teach, plus the foundations course (closing paths that bypass
the entry point, restoring from a backup).

## What you will be able to do

- Deliver two services behind HAProxy: routing by name, HTTPS with a
  certificate per name, and a renewal cycle you wrote and can replay.
- Control access to administration, keep a client from choosing its own
  address, limit a noisy client and release it, and close every path that
  bypasses the entry point.
- Let a long event stream through, and read a stopped service and refusals in
  the metrics.
- Lose HAProxy, its configuration and the business data, and restore them from
  backups, then show everything comes back by itself after a reboot.
- Diagnose a fault you were not told about from the configuration, the state
  of the servers and the journal, and repair it without removing a safeguard.
