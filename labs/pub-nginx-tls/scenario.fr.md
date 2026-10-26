# Scénario

Une autorité ACME locale tourne sur la machine, un client ACME est
disponible en image, deux noms doivent être servis en HTTPS,
`app.lab.test` et `api.lab.test`, et **aucun certificat n'existe**. Nginx
publie l'application en clair, et sert déjà le chemin du défi HTTP-01.

Le banc est décrit dans `/opt/pub-nginx-tls/LISEZ-MOI.txt`.

## Mission

Obtenez les certificats, servez les deux noms en HTTPS, protégez les clés,
et rendez le renouvellement automatique et vérifiable.

## Ce que la validation appellera, et pourquoi

Un renouvellement peut se déclencher par une minuterie systemd, par cron,
ou par un hook du client ACME. Exiger l'un de ces mécanismes reviendrait à
noter un choix d'implémentation plutôt qu'un résultat.

Fournissez donc un point d'entrée exécutable :

```
/usr/local/bin/renouveler-certificats
```

La validation l'appelle, puis mesure la **nouvelle série réellement
servie**. La façon dont vous l'obtenez vous appartient.

## Trois pièges mesurés

**L'autorité racine de Pebble change à chaque démarrage.** C'est voulu par
ses auteurs. Elle se récupère sur `/roots/0`, jamais ne se suppose, et le
test lui-même la récupère plutôt que de l'écrire en dur.

**Le défi HTTP-01 se sert en clair, par un `location` placé avant toute
redirection.** On lit souvent qu'une redirection globale vers HTTPS empêche
la validation. C'est trop affirmatif : le validateur de Let's Encrypt suit
les redirections, jusqu'à dix, vers les ports 80 et 443, et ne vérifie pas
le certificat de la cible. Chez lui, une redirection globale passe donc
souvent.

Ce qui reste vrai, et qui est la raison de la règle : une redirection place
le défi hors de votre contrôle. Elle le fait dépendre de ce que l'autorité
accepte de suivre, et toutes ne suivent pas. Elle échoue à la **première**
émission, puisqu'il n'y a encore rien à joindre en 443. Et elle casse dès
que la cible sort des deux ports autorisés. Servir le défi en clair ne
dépend, lui, que de votre configuration.

**Effacer le compte ACME pour repartir de zéro fonctionne**, et c'est
exactement ce qu'il ne faut pas faire : face à une autorité réelle, chaque
inscription consomme un quota et perd l'historique. Le test compare le
compte avant et après le renouvellement.

## Ce qui est vérifié

- **critique** : depuis `poste.lab`, le client **valide** la chaîne pour les
  deux noms. Pas de `-k` : c'est justement la validation qu'on mesure ;
- le renouvellement sert une **nouvelle série**, sans redémarrer le
  processus Nginx, et sans changer le compte ACME ;
- **critique** : ni les clés privées ni le compte ne sont lisibles par tout
  le monde, et le service répond toujours ;
- **critique** : TLS reste correct après un reload, puis après un reboot.

Le dernier test coupe la machine, il est donc joué en dernier.
