# Scenario

The machine carries an Nginx installed from the distribution package, and
nothing else: the demonstration site has been removed, no service is
published, and the service is **stopped and not enabled at boot**.

The backend to publish already listens on `127.0.0.1:18092`. What the
installation must present is written in
`/opt/pub-nginx-installation/manifeste.txt`.

## Mission

Publish `app.lab.test` towards the backend, following the manifest. Then
show you can tell apart the three gestures people confuse most: validate,
reload, restart.

## The four checks, and why the last one decides

1. **What runs follows the manifest.** The version read from the binary is
   compared with the one the manifest announces, not with a value hard-coded
   in the test: a test claiming "1.24" would become wrong the day the
   distribution moves, with no way to say who is at fault.

2. **A misplaced directive is refused**, and the service holds. Both halves
   count: refusing a faulty configuration is worth nothing if the service
   falls at the same time, which is exactly what a `restart` issued without
   prior validation produces.

3. **A valid change applies without replacing the master process.** The test
   compares the PID before and after: that is what tells a reload from a
   restart, and the distinction is not theoretical, since a restart drops
   live connections.

4. **The service comes back after a machine reboot.** This is the check that
   decides: a service answering today and not coming back tomorrow is not
   installed, it is started. The difference only shows by rebooting for
   real, and the test does.

That last test cuts the machine. It therefore runs last: anything following
it would measure a different state.
