# Scénario

Deux générations de l'application sont installées. La **1.4.2** est en
service, la **1.5.0** est disponible et arrêtée. Rien ne permet de passer de
l'une à l'autre : c'est ce que vous livrez.

Le plan est dans `/opt/pub-haproxy-mise-a-jour/plan.txt`, les générations et
les chemins dans `manifeste.txt`.

## Ce que ce lab mesure et que les autres ne mesurent pas

**Le couple maître-ouvriers.** Un rechargement de HAProxy ne remplace pas le
processus maître : il lui fait démarrer de **nouveaux** ouvriers, et laisse
les **anciens** vivre jusqu'à ce que les connexions qu'ils tiennent se
terminent. Les deux générations d'ouvriers coexistent donc quelques minutes.

C'est exactement ce qui rend un rechargement sans coupure possible, et c'est
aussi ce qui impose une règle que le plan énonce : **une livraison ne retire
pas la génération qu'elle remplace.** Les anciens ouvriers lui parlent
encore. Elle retire celle qui avait été remplacée à la livraison précédente.

Le maître, lui, tient les sockets d'écoute. Le remplacer ferme le port, et
aucune mesure côté client ne rattrape une seconde pendant laquelle rien
n'écoute. Le test compare donc son PID avant et après.

## Les cinq contrôles

1. **L'état de départ**, et les deux exécutables `livrer` et `revenir`
   présents et exécutables.

2. **La livraison amène la version du plan sans couper.** La validation
   ouvre un flux long, lance une sonde continue, **exécute votre `livrer
   1.5.0`**, et mesure pendant la bascule : au plus une requête courte en
   échec, le flux long qui continue de recevoir et va jusqu'à son terme, le
   PID du maître inchangé, et de nouveaux ouvriers apparus.

3. **Le retour restaure la génération**, avec la même exigence de
   disponibilité. Contrôle critique.

4. **Le journal dit ce qui a été mesuré.** Relu par un humain.

5. **Tout revient après un redémarrage.** Contrôle critique, et dernier
   puisqu'il coupe la machine.
