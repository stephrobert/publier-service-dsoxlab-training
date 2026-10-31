# La tâche

Travaillez depuis `edge.lab` pour le côté opérateur et depuis `poste.lab` pour
le côté client. Le banc est décrit dans `/opt/pub-epreuve-nginx/LISEZ-MOI.txt`.
Depuis `poste.lab`, récupérez la racine de l'autorité de test sur
`https://<ip-edge>:15000/roots/0` (le `-k` ne sert qu'à joindre l'interface de
gestion de Pebble, jamais le service) et utilisez
`curl --cacert <racine> --resolve <nom>:443:<ip-edge>`.

Le scénario liste les livrables, les points d'entrée que la validation appelle
et les emplacements fixes. En bref :

1. **Publier** `www.epreuve.test` (le site, depuis
   `/opt/pub-epreuve-nginx/site`) et `api.epreuve.test` (l'API sur
   `127.0.0.1:18201`), HTTPS strict, HTTP qui redirige, noms inconnus refusés.
   Fournir `renouveler-certificats`.
2. **Fixer la politique** : `/admin` derrière les identifiants fournis, fichiers
   cachés refusés, seulement `GET` et `HEAD` sur l'API, backend inaccessible
   depuis le réseau, réponse publique de l'API mise en cache, réponses privées
   jamais partagées.
3. **Exploiter** : `/v1/flux` en flux continu, journal JSON dans
   `/var/log/nginx/epreuve.json`, page d'état sur `127.0.0.1:8081`, et
   `sonde-alerte`.
4. **Incident** : écrivez `/home/student/recette-initiale.md` quand votre
   recette passe. Un incident suit. Écrivez `/home/student/incident.yaml` :

   ```yaml
   couche: tls    # une parmi : amont, tls, droits, entetes
   composant: "..."
   explication: "..."
   ```

   Ne nommez dans `composant` que la vraie cause ; les hypothèses écartées ont
   leur place dans `explication`. Réparez par le plus petit changement, sans
   rien affaiblir, et prouvez que le service répond de nouveau, plusieurs fois
   de suite.
5. **Reprise** : fournissez `sauvegarder-service` et `restaurer-service`. La
   validation détruit la configuration et les fichiers de certificat, lance
   votre restauration, redémarre la machine et rejoue toute la recette.
