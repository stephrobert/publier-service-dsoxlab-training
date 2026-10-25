# Scénario

Vous prenez en charge un déploiement Traefik que vous ne connaissez pas. Les
utilisateurs signalent que le service `app.lab.test` est indisponible. La route
d'administration n'a pas été revue et le proxy ne dispose pas d'une supervision
exploitable.

## Mission

En 75 minutes, sécurisez l'administration, ajoutez des en-têtes de sécurité et
une limitation de débit, configurez les journaux JSON filtrés et les métriques
Prometheus avec une alerte sur les réponses 5xx, puis rétablissez l'application.

L'incident initial n'est pas documenté. Appuyez-vous sur la réponse HTTP
observée et les journaux Traefik pour identifier le composant défaillant.
Consignez le symptôme, la preuve tirée des journaux, la cause, la correction et
la réponse obtenue après réparation dans
`/opt/pub-epreuve-niveau-deux/incident-report.txt`.

Aucun indice n'est fourni. Le corrigé de référence ne figure pas dans les
guides.
