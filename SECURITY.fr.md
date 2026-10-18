# Politique de sécurité

## Ce que contient ce dépôt

Un catalogue de labs de formation : des fichiers déclaratifs (`meta.yml`,
`lab.yaml`), des énoncés en Markdown, des playbooks Ansible et des tests
`pytest`. **Il n'exécute rien par lui-même** : les labs sont joués par la CLI
`dsoxlab`, qui vit dans son propre dépôt.

## Signaler une vulnérabilité

N'ouvre **pas** d'issue publique. Emploie le signalement privé de GitHub sur ce
dépôt, ou écris aux mainteneurs.

Indique ce que tu as trouvé, comment le reproduire, et l'impact que tu lui
prêtes. Tu recevras un accusé de réception, puis une correction ou l'explication
de pourquoi ce n'en est pas une.

## Ce qui compte comme une vulnérabilité ici

- **Un secret commité par erreur** : un jeton, une clé privée, un mot de passe
  de vault. Signale-le même s'il semble révoqué : il reste dans l'historique
  git.
- **Un lab qui exécute sur le poste de l'apprenant autre chose** que ce que son
  énoncé annonce.
- **Une solution de référence lisible en clair** là où elle est censée être
  chiffrée : ce n'est pas une faille du système, mais cela détruit l'exercice.

## Ce qui n'en est pas

Un lab qui monte délibérément un système vulnérable enseigne précisément ce
sujet, ce n'est pas un défaut. Un lab qui demande d'affaiblir une configuration
le fait dans sa propre machine, que `dsoxlab destroy` rend.
