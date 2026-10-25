# The task

Fix `/opt/pub-modele/dynamic/routes.yaml` so that `modele-a.lab.test` reaches
backend `app-a`, and `modele-b.lab.test` reaches the Docker-provider service
named `cible` (not the file-provider decoy of the same name). Remove whatever
makes an unplanned hostname answer with an application. The check calls the
real HTTP entrypoint on port 80 and reads the response body.
