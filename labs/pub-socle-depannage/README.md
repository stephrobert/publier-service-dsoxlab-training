# pub-socle-depannage

**Audience:** the learner.

A production incident rarely announces its layer. This lab hands you a
published service, `depan.test` on `edge.lab`, carrying exactly one fault
drawn at random among DNS, transport, TLS, the route, and the backend, plus
background noise that has nothing to do with it.

## What you will be able to do

- Form a hypothesis from observation and confirm or refute it with a
  targeted test, keeping a timestamped log of what you tried and found.
- Name the actual faulty layer and component, distinct from any plausible
  but wrong guess and from the unrelated noise in the logs.
- Repair the fault with a minimal, targeted change and prove the healthy
  routes still work afterward, including against a freshly drawn retest.
- Prove that no protection was removed to make the service answer again:
  the forbidden route stays forbidden, the backend stays unreachable
  directly, and TLS stays mandatory.
