# Scenario

The proxy works. Its administration socket is **mode 666**, at `level
admin`, and there is no state file. Three things follow, and none of them
breaks anything:

1. **Any account on the machine can drive the proxy.** See for yourself, the
   `intrus` identity belongs to no group:

   ```bash
   sudo -u intrus sh -c "echo 'show info' | socat -t2 stdio /run/haproxy/admin.sock"
   ```

2. **Reading and acting are not separated.** Everything that needs to read
   the state, a metrics collector, a probe, a monitoring script, gets the
   right to act.

3. **A reload forgets every decision taken at runtime.** The server you just
   took out of service comes back at the first `reload` triggered by
   something else, a certificate renewal for instance.

Three test identities exist: `veilleur` who must be able to read,
`exploitant` who must be able to act, and `intrus` who must be able to do
neither. Everything is described in `/opt/pub-haproxy-runtime/recette.txt`.

## The four checks

1. **Only the intended identity has the administration operations.** This
   check is critical and plays all three identities: `veilleur` reads and
   cannot act, `exploitant` acts, `intrus` can do neither. No destructive
   operation is played: taking a server out and back is enough to prove the
   right.

2. **Taking a server out really changes the assignment.** The reported state
   is not enough: the test sends traffic and reads which instance answers. A
   server marked as leaving that keeps serving is a state, not a decision.

3. **The decision survives a reload.** The test takes the server out,
   reloads, and looks at the state HAProxy **reports**. A marker file left
   next to it does not answer the requirement: HAProxy is the one that must
   remember, because it is the one deciding where the next request goes.

4. **The return to nominal is documented and executed.** The method is
   delivered as an executable, because the validation runs it: a return
   method that has never been played is not a return method. The dossier is
   read by a human.
