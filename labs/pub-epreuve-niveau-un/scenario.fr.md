# Scénario

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
