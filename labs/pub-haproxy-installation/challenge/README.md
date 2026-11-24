# Scenario

The machine carries a HAProxy installed from the distribution package, and a
configuration that holds **no listener at all**: no `frontend`, no `listen`.
HAProxy refuses to start on such a configuration, and the message it returns
is the first thing to learn to read.

Three services already run on the loopback. Two speak HTTP and return their
name, the `Host` they received and the address the proxy forwarded to them.
The third does **not** speak HTTP: it answers any line by echoing it back
with a prefix, including an HTTP request line.

What the installation must present is written in
`/opt/pub-haproxy-installation/manifeste.txt`. The version there is **read
from the installed binary**, not copied, so it follows the distribution.

## Mission

Publish both HTTP names on port 80 and the line service as a TCP relay on
port 7001, from the same instance. Open the stats page and the runtime
socket, and make sure neither is reachable from the network.

## The four checks

1. **What runs matches the manifest.** The version is read from the binary
   systemd actually executes, resolved through `/proc/<pid>/exe`, not from the
   first `haproxy` the `PATH` offers. `maxconn` and `nbthread` are read
   **through the runtime socket**, so from the live instance: a value written
   in a file that was never loaded does not count.

2. **HTTP mode routes both names and forwards the client address.** The
   service prints the `X-Forwarded-For` it received, and the test compares it
   to the client's real address. A header the proxy declared to itself would
   prove nothing: the backend is the witness.

3. **TCP mode relays without understanding**, and the check runs in both
   directions. On port 7001, a deliberately invalid HTTP request line must be
   **relayed** and come back as an echo. On port 80, the same line must be
   **refused** by HAProxy before it reaches anything. If both ports behaved
   the same, both frontends are in the same mode, whatever the directives say.

4. **Stats and administration are not public.** This check is critical, and it
   reads no configuration file: it enumerates the sockets HAProxy really
   listens on, and accepts nothing outside the loopback but ports 80 and 7001.
   It requires at the same time that the stats page answer from the machine and
   that the runtime socket answer `show info`: you therefore cannot satisfy it
   by deleting what it watches.

The last test reboots the machine, then replays checks 2, 3 and 4. A service
that answers today and does not come back tomorrow is not installed, it was
started.
