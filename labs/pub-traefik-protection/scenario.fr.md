# Protéger l'administration de Traefik

Sur `edge.lab`, une instance de Traefik expose actuellement son API
d'administration directement sur le port 8080. Toute personne qui atteint ce
port peut consulter la configuration du proxy sans s'authentifier.

## Mission

Supprimez cet accès direct et fournissez un point d'administration HTTPS
protégé par authentification sur `admin.lab.test`. L'API Docker doit être
accessible à Traefik par un proxy de socket restreint, jamais par un montage du
socket dans Traefik. Ajoutez des en-têtes de sécurité et une limite de débit
qui renvoie 429 sous charge. Un opérateur autorisé doit pouvoir consulter le
tableau de bord et l'API ; sans identifiants, les deux doivent refuser l'accès.

Le certificat de test, les identifiants de validation, l'image du proxy et le
chemin de travail sont décrits dans `/opt/pub-admin/LISEZ-MOI.txt`.
