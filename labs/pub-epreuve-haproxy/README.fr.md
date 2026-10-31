# pub-epreuve-haproxy

**Public :** l'apprenant.

C'est l'épreuve de fin du module HAProxy. HAProxy est installé et n'a aucune
mission ; deux services tournent derrière lui, démarrés à la hâte ; une seconde
instance HAProxy, `archives`, porte une panne non annoncée. On vous donne un
besoin et une recette, jamais une configuration à recopier.

```bash
dsoxlab run pub-epreuve-haproxy
dsoxlab challenge pub-epreuve-haproxy
dsoxlab check pub-epreuve-haproxy
```

L'épreuve se passe en fin de module : elle n'exige que ce que les leçons
HAProxy enseignent, plus les fondamentaux (fermer ce qui contourne le point
d'entrée, restaurer depuis une sauvegarde).

## Ce que vous saurez faire

- Livrer deux services derrière HAProxy : routage par nom, HTTPS avec un
  certificat par nom, et un cycle de renouvellement que vous avez écrit et que
  vous savez rejouer.
- Contrôler l'accès à l'administration, empêcher un client de choisir son
  adresse, limiter un client bruyant puis le relâcher, et fermer tout ce qui
  contourne le point d'entrée.
- Laisser passer un flux d'événements long, et lire un service arrêté et des
  refus dans les métriques.
- Perdre HAProxy, sa configuration et la donnée métier, les restaurer depuis
  des sauvegardes, puis montrer que tout revient seul après un redémarrage.
- Diagnostiquer une panne qu'on ne vous a pas annoncée à partir de la
  configuration, de l'état des serveurs et du journal, et la réparer sans
  retirer une protection.
