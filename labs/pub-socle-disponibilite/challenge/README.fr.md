# La tâche

Sur `edge.lab`, éditez `/etc/pub-disp/politique.yaml` pour que les quatre
points ci-dessous tiennent. Rien d'autre n'est à écrire : les tests
observent directement le répartiteur et les backends, avec le sondeur
déjà installé là-bas. La politique est relue à chaque sonde et à chaque
requête, sans redémarrage nécessaire.

```yaml
repartition:
  actif: <true|false : le répartiteur alterne-t-il réellement entre
    chaque backend qu'il tient pour sain, au lieu de toujours coller au
    premier qui répond ?>
probe:
  intervalle_s: <combien de secondes entre deux sondes de santé : assez
    bas pour que retirer ou rétablir un backend se produise dans une
    fenêtre que vous pouvez défendre>
  echecs_avant_retrait: <combien de sondes consécutives en échec avant
    qu'un backend sain soit retiré de la rotation : assez bas pour
    réagir, assez haut pour ne pas sur-réagir à une seule sonde
    capricieuse>
  succes_avant_retour: <combien de sondes consécutives réussies avant
    qu'un backend retiré revienne dans la rotation : même compromis, au
    retour>
```

Lisez `/home/student/README-disp` pour les ports exacts de cette session.
Utilisez le sondeur fourni pour vérifier votre propre travail avant de
vous reposer sur les tests :

```sh
sudo -u student python3 /opt/pub-disp/sonder.py echantillon <port_repartiteur> <n>
sudo -u student python3 /opt/pub-disp/sonder.py direct <port_backend>
sudo -u student python3 /opt/pub-disp/sonder.py indisponible <port>
```

Simulez une panne applicative d'un backend avec
`sudo touch /var/lib/pub-disp/malsain-a` (ou `-b`) ; retirez le fichier
pour le rétablir.

Les tests font les mêmes vérifications eux-mêmes, depuis `edge.lab`, y
compris arrêter le répartiteur pour prouver ce qu'un seul exemplaire ne
peut pas survivre ; ils le redémarrent ensuite dans tous les cas.
