# Épreuve : publier et rétablir les services

## Critères

- Deux services HTTPS distincts répondent depuis l'hôte de contrôle, hors VM.
- Traefik sert un certificat renouvelé et émis par l'autorité Pebble active.
- L'hôte de contrôle ne peut joindre directement ni les backends ni
  l'administration.
- Les deux services HTTPS reviennent après le redémarrage du moteur Docker.
- L'épreuve est terminée en 60 minutes ; aucun indice n'est fourni.

Le corrigé de référence ne figure pas dans les guides.
