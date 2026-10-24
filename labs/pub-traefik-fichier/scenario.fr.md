# Scénario

Traefik tourne déjà sur `edge.lab`. Un petit service web est géré par systemd,
mais les clients ne peuvent pas l'atteindre par le proxy. Le service écoute sur
le port `18081` ; l'adresse publique demandée est
`http://systemd.lab.test/`.

## Mission

Publiez le service hôte avec le fournisseur fichier de Traefik. Rendez la route
accessible et prouvez que Traefik charge la configuration dynamique sans être
redémarré.
