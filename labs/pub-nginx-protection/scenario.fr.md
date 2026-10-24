# Scénario

Nginx publie déjà l'application, mais le proxy accepte les requêtes
d'administration sans protection, sert les fichiers cachés et transmet des
méthodes dont l'application n'a pas besoin.

## Mission

Ajoutez les en-têtes de sécurité, exigez les identifiants fournis sur
`/admin`, refusez les fichiers cachés et bloquez les méthodes d'écriture
inutiles sans casser les requêtes normales de l'application.
