# La tâche

Corrigez `/opt/pub-modele/dynamic/routes.yaml` pour que `modele-a.lab.test`
atteigne le backend `app-a`, et que `modele-b.lab.test` atteigne le service du
provider Docker nommé `cible` (pas le leurre de même nom du provider fichier).
Supprimez ce qui fait qu'un nom non prévu répond avec une application. La
notation appelle le véritable point d'entrée HTTP sur le port 80 et lit le
corps de la réponse.
