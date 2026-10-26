# Scénario

`zds.lab.test` est servi par deux points d'entrée Traefik jumeaux sur
`edge.lab` (ports lisibles dans `/opt/pub-zds/ports.env`), tous deux
surveillant exactement la même configuration dynamique et servant
exactement le même certificat. Le trafic de production est câblé en dur
sur le backend `v1` ; une candidate `v2` tourne déjà, saine, et joignable
sur le réseau Docker, mais rien dans la configuration actuelle ne permet
d'y déplacer le trafic progressivement, et rien ne retire un backend de la
rotation s'il cesse de répondre correctement : le service réparti ne porte
aucune sonde de santé. Un outil de rotation de certificat,
`/opt/pub-zds/outils/tourner-certificat.sh`, est partagé par les deux
points d'entrée ; il a été écrit en supposant qu'il ne tourne jamais qu'une
fois à la fois, ce qui n'est pas une hypothèse sûre pour un outil destiné à
servir deux points d'entrée indépendants.

## Mission

Lisez `/opt/pub-zds/README`, puis :

- Construisez un vrai chemin progressif de `v1` vers `v2` : **deux
  serveurs pondérés d'un même service Traefik réparti**, et non un service
  de type `weighted` combinant deux sous-services séparés. Montrez le
  trafic circuler par les deux versions pendant la transition, avec une
  part d'erreurs bornée.
- Ajoutez une sonde de santé au répartiteur du service pour que, lorsque
  `v2` est marquée malsaine (son marqueur `/app/healthy` retiré, simulant
  une vraie panne), elle soit réellement retirée de la rotation et que le
  trafic revienne à `v1` sans qu'un humain n'édite quoi que ce soit à la
  main.
- Depuis `poste.lab`, observez ce qui se passe quand on arrête le
  processus d'un point d'entrée (l'autre doit continuer à servir), et ce
  qui se passe quand l'hôte unique qui porte les deux points d'entrée
  devient injoignable (les deux s'arrêtent nécessairement, puisqu'ils
  partagent un seul domaine de panne). Écrivez votre conclusion, pour
  chacune des deux pannes, sous la forme `survit` ou `ne_survit_pas`, dans
  `/home/student/domaine-de-panne.yaml` :

  ```yaml
  perte_processus: survit
  perte_hote: ne_survit_pas
  ```

  Ne devinez pas : déclenchez chaque panne pour de vrai et observez le
  point de vue du client avant d'écrire le fichier. Prétendre à une
  résilience que ce lab à une seule VM n'a pas est pire que d'en admettre
  la limite.
- Corrigez `/opt/pub-zds/outils/tourner-certificat.sh` pour qu'une
  exécution double, en même temps, depuis les deux points d'entrée, ne
  laisse jamais une paire certificat/clé dépareillée ou illisible dans le
  stockage partagé ; les deux points d'entrée doivent continuer à servir
  du TLS valide ensuite.
