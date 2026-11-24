# Épreuve : publier et rétablir les services

## La situation

Vous intervenez pendant la fenêtre de changement d'une petite plateforme web.
Deux services doivent être publiés derrière un point d'entrée Traefik. Les
images des backends et l'autorité ACME de test sont disponibles sur la machine.

## Mission

Publiez les deux services en HTTPS avec des certificats renouvelés
automatiquement. Vérifiez qu'un client extérieur à la VM peut joindre les
services, mais ne peut accéder directement ni aux backends ni à
l'administration. Configurez la reprise après redémarrage de Docker et prouvez
que les deux services reviennent après le redémarrage du moteur.

Cette épreuve dure 60 minutes et ne fournit aucun indice. Le contrôle final
envoie les requêtes depuis l'hôte de contrôle, à l'extérieur de la VM, observe
l'émission et le renouvellement des certificats, vérifie les ports bloqués et
redémarre Docker.

## Ce qui est demandé

### Critères

- Deux services HTTPS distincts répondent depuis l'hôte de contrôle, hors VM.
- Traefik sert un certificat renouvelé et émis par l'autorité Pebble active.
- L'hôte de contrôle ne peut joindre directement ni les backends ni
  l'administration.
- Les deux services HTTPS reviennent après le redémarrage du moteur Docker.
- L'épreuve est terminée en 60 minutes ; aucun indice n'est fourni.

Le corrigé de référence ne figure pas dans les guides.
