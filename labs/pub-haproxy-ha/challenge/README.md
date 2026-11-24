# Scenario

Two machines serve the same service, with the same configuration and **the
same certificate**. Each answers on its own address. Nothing makes them one
entry point: the service address `10.10.110.200` belongs to neither.

`keepalived` is installed and **not configured**. Deploying the failover is
the mission.

Everything is described in `/opt/pub-haproxy-ha/recette.txt`.

## What the fixture already settled for you, and why

Both proxies listen on `:443` rather than on a specific address. A listener
on an address that does not exist yet refuses to start, and the service
address exists on neither machine at rest. That is the most common trap of
this family, and it is avoided here so that you work on the failover rather
than on a service that will not start.

## The four checks

1. **Both entry points serve the recipe.** Each on its own address, with
   strict TLS, before any failover. A pair whose member does not serve is
   not a pair, it is a machine and a witness.

2. **Losing a process, then a host, causes a measured recovery.** The
   validation stops HAProxy on the machine holding the address, then reboots
   that whole machine. In both cases it probes **without changing anything
   on the client side**: that is the whole difference between a failover and
   an intervention.

   The first case is the more instructive. A failover that only watches the
   machine does not see a dead proxy on a live machine: the address stays
   where it is, and the service is down while high availability is doing
   fine.

3. **Policy and certificates stay consistent.** Critical check. Both entry
   points present the **same certificate fingerprint**, and the private
   route stays refused **after** the failover. A policy that does not follow
   the service is an opening that does not know itself.

4. **The dossier describes what this failover does not protect.** Read by a
   human. Three subjects are expected, and none is readable in the
   configuration: the network partition and the double master it produces,
   the state that is not replicated, and what the failover does not cover at
   all.
