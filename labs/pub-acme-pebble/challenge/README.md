# Challenge: a certificate nobody typed by hand

You work in `/opt/pub-lab` on `edge.lab`.

## What is expected

1. Pebble runs in a container, without the "always valid" shortcut, and
   answers on `https://localhost:14000/dir`; its management API answers on
   `https://localhost:15000`.
2. `/opt/pub-lab/lego/certificates/app.lab.test.crt` exists, is issued by this
   Pebble (its chain verifies against the roots Pebble serves), names
   `app.lab.test`, and matches its private key.
3. The validation really happened: Pebble's log shows the HTTP-01 challenge for
   `app.lab.test`.

## What is proven

The tests question Pebble and the certificate, never your Compose file.
