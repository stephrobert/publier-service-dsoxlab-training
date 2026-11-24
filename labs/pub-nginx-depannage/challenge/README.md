# Scenario

A publication stack was healthy. It fronts a static page, two backends, and
a control route. A **real** fault has been injected into it, drawn at random
from five families:

- **selection**: a route reaches the wrong backend;
- **permission**: a file or directory is no longer readable by whoever
  serves it;
- **resolution**: the backend's name no longer resolves;
- **TLS trust**: the proxy's trust store no longer recognises the backend's
  certificate;
- **timeout**: a wait bound became shorter than the service.

You do not know which. And there is **noise** around it: a `server` block
for an abandoned domain name, a `conf.d/` file holding nothing but comments,
a duplicated `gzip on`, a commented-out `proxy_pass` carrying a wrong port.
Each looks suspicious. None explains the fault.

## Mission

Find the fault, repair it, and verify **the whole** acceptance list, which
is in `/opt/pub-nginx-depannage/recette.txt`.

Also write `/opt/pub-nginx-depannage/diagnostic.md`: the component in cause,
the cause, and the observations that led you there.

## What the validation judges, and what a reviewer reads

The automated validation does not know which variant is active, so it cannot
check "the right fix". It measures the **final state of the acceptance
list**, the same one for all five variants. That is also the right way round:
after an outage you do not replay the test for the thing you just repaired,
you replay the whole list. That is how you catch the fix that repaired one
thing by breaking another.

Of the diagnosis file it judges **presence** and the fact that it names a
component. It does not judge the reasoning, and does not pretend to: a
reviewer reads that. A check that graded the quality of an explanation would
in fact be grading the presence of keywords, and would teach people to sow
them.

## The two loosenings the acceptance list forbids

Two variants can be "repaired" by loosening something, and both would work:

- `proxy_ssl_verify off` closes the TLS variant by accepting any backend
  certificate;
- running the workers as `root` closes the permission variant without
  touching any permission.

The stack therefore carries a **trust probe**, `/api-secondaire/`, pointing
at a backend whose certificate comes from another authority and whose SAN
does not match. It must answer **502**, and that is all it must do. If it
answers 200, TLS verification has been loosened. Both checks are
**critical**.

## What is verified

- the static root, `/app/` and `/api/` each return **their own** marker. The
  three differ: a route that reaches the neighbouring backend answers 200
  without complaining, and only the marker says so;
- `/api/lent` passes, and a request that never advances is cut by the proxy
  in under fifteen seconds, with a **504**. A `000` means curl gave up, not
  the proxy;
- **critical**: workers do not run as `root`, backend ports are not
  reachable from the network, and the static root is not world-writable;
- **critical**: the trust probe answers 502, and `/api/` answers 200.
  Verification that also refuses the legitimate backend has verified
  nothing; it has closed everything.

## Where to look

- `systemctl status nginx` and `nginx -t` say a lot when the service will not
  start, and they say it by naming the file and the line.
- `nginx -T` prints the **effective** configuration with every `include`
  resolved: what Nginx reads, as opposed to what you think you wrote for it.
- `/var/log/nginx/error.log` separates a permission 403 from a trust 502, and
  names the file or certificate in cause.
- `curl -v` from the machine itself separates what is broken in the proxy
  from what is broken in the backend.
- A `location`'s selection order is not the writing order: `=`, then `^~`,
  then regular expressions in file order, then the longest prefix.
