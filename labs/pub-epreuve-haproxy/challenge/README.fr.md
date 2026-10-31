# La mission

Travaillez depuis `poste.lab` pour tout ce que voit un client, et depuis
`edge.lab` pour tout ce que fait un opérateur. `/home/student/racine-acme.pem`
sur `poste.lab` est la racine de l'autorité de test : n'utilisez jamais
`curl -k` / `--insecure`. Lisez en entier `/home/student/README-epreuve` et
`/opt/pub-epreuve-haproxy/recette.txt` sur `edge.lab` : ils disent ce qui doit
arriver.

L'épreuve a deux parties indépendantes. Budget de temps : 150 minutes.

1. **Livrer deux services (domaines : publication, sécurité, observabilité,
   reprise).** HAProxy est installé et n'a aucune mission. Les services
   `catalogue` et `notifications` tournent sur les ports 18301 et 18302,
   démarrés à la hâte. Livrez, avec la configuration de HAProxy et deux
   scripts :

   - les deux noms en HTTPS, un certificat par nom, obtenus auprès de
     l'autorité de test par le client ACME fourni ;
   - `/opt/pub-epreuve-haproxy/renouveler`, exécutable, qui renouvelle les deux
     certificats et les met en service sans redémarrer HAProxy. La validation
     l'**exécute**, plusieurs fois, et de nouveau après un redémarrage ;
   - les exigences de la recette sur l'accès, l'adresse source, la limitation
     de débit, l'isolement, le flux et les métriques ;
   - la sauvegarde de votre configuration dans
     `/var/backups/pub-epreuve-haproxy/haproxy.cfg.bak`, et
     `/opt/pub-epreuve-haproxy/restaurer`, exécutable, qui restaure la donnée
     métier du catalogue **et** la configuration de HAProxy depuis les
     sauvegardes, puis remet HAProxy en service. La validation casse les trois,
     puis l'exécute.

2. **Diagnostiquer une panne inconnue (domaine : diagnostic).** L'instance
   `archives` (port 8088, sa propre configuration, son unité et son socket,
   listés dans la recette) porte une panne tirée parmi cinq familles. Réparez-la
   sans retirer aucune protection, puis écrivez `/home/student/incident.yaml`
   sur `edge.lab` :

   ```yaml
   famille: routage    # un parmi : routage, sonde, confiance, limite, delai
   composant: "..."
   explication: "..."
   ```

   Nommez la cause réelle, appuyée sur ce que vous avez observé. Citer toutes
   les familles « au cas où » n'est pas un diagnostic. Les hypothèses que vous
   avez écartées ont leur place dans `explication`.
