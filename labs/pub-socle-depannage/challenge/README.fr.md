# La mission

Travaillez depuis `poste.lab` pour tout ce qui concerne le client, et depuis
`edge.lab` pour tout ce qui concerne l'opérateur. `/home/student/ca.pem` sur
`poste.lab` est l'autorité de test : n'utilisez jamais `curl -k` /
`--insecure`.

1. Observez depuis `poste.lab` : `dig depan.test A`, puis
   `curl --cacert ca.pem --resolve depan.test:443:<ip-edge>
   https://depan.test/`. Une couche parmi cinq est cassée : DNS, transport
   (rien ne répond sur 443), TLS (le certificat n'est pas de confiance), la
   route (le routeur répond mais l'appel au backend échoue), ou le backend
   (connexion refusée en amont). Un avertissement de fond peut apparaître
   dans `journalctl` sur `edge.lab` ; il est sans rapport, ce n'est pas un
   indice.

   Tenez `/home/student/journal.md` sur `edge.lab` pendant votre enquête :
   des observations horodatées, l'hypothèse que vous formulez, le test
   ciblé mené, et s'il l'a confirmée ou réfutée.

2. Une fois la couche et le composant réels connus, écrivez
   `/home/student/diagnostic.yaml` sur `edge.lab` :

   ```yaml
   couche: route    # l'une de : dns, transport, tls, route, backend
   composant: "..."
   explication: "..."
   ```

   Ne nommez que la cause réelle. Lister toutes les couches possibles « au
   cas où » ne constitue pas un diagnostic.

3. Réparez sur `edge.lab` par la plus petite correction qui fonctionne. Les
   fichiers concernés vivent sous `/etc/pub-dep/` (`route.yaml`), les unités
   systemd `pub-dep-router.service` et `pub-dep-backend.service`, et la zone
   unbound dans `/etc/unbound/unbound.conf.d/pub-dep.conf`.

4. Prouvez depuis `poste.lab`, après correction : le service répond `200`
   sur `/` (retesté trois fois), `/admin` répond encore `403`, le port du
   backend reste injoignable directement, et le port 443 ne parle encore
   que TLS. Ces trois protections n'existaient pas pour être cassées par
   votre correction ; elles existent pour vérifier que votre correction ne
   les a pas cassées non plus.
