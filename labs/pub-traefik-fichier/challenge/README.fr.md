# La tâche

Routez `http://systemd.lab.test/` vers le backend géré par systemd avec
l'instance Traefik déjà lancée. Traefik surveille
`/opt/pub-fichier/dynamic/`. La notation appelle le véritable endpoint et
confirme que Traefik n'a pas été redémarré.
