# Scénario

La fenêtre de changement est ouverte. Le proxy inverse utilise Traefik v3.7.6
et les utilisateurs signalent que le service publié est indisponible. Examinez
la version active, la configuration et les notes de version avant de modifier
le déploiement.

## Mission

Mettez Traefik à niveau vers la v3.7.15 avec l'image épinglée, rétablissez la
route attendue et vérifiez la réponse du service actif. Conservez une définition
de retour arrière vers la version connue comme fonctionnelle. Le contrôle
automatisé exécutera ce retour arrière, vérifiera que l'ancienne version sert
le trafic, puis restaurera la version mise à niveau.

La mise à niveau reste dans Traefik v3. Le guide de migration v2-vers-v3 donne
un contexte utile pour une future migration majeure, mais ses changements
incompatibles ne font pas partie de cette mise à jour corrective.
