# Scénario

HAProxy publie déjà l'application, mais `/admin` est joignable depuis
n'importe quelle adresse, un client peut envoyer un nombre illimité de
requêtes, et les réponses ne portent aucun en-tête de sécurité.

## Mission

N'autorisez `/admin` que depuis la boucle locale `127.0.0.1` et répondez `403`
à toute autre source. Répondez `429` à un client qui envoie plus de 20
requêtes en 10 secondes. Ajoutez `X-Content-Type-Options: nosniff` et
`X-Frame-Options: DENY` à toutes les réponses. Les requêtes ordinaires
doivent continuer à fonctionner.
