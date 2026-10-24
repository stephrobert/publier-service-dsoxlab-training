# The task

Route `http://systemd.lab.test/` through the running Traefik instance to the
systemd-managed backend. Traefik already watches `/opt/pub-fichier/dynamic/`.
The check calls the real endpoint and confirms Traefik was not restarted.
