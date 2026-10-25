# Scénario

Une petite application tourne sur la VM, mais Nginx ne la publie pas encore.
Le conteneur et sa configuration de départ sont prêts à être complétés.

## Mission

Configurez Nginx pour agir en reverse proxy de `app.lab.test` vers
l'application locale. Préservez le chemin et l'hôte de la requête, puis
transmettez les en-têtes attendus d'une application derrière un proxy.
