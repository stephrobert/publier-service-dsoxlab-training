# Protéger l'administration de Traefik

## La situation

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

## Défi : administration Traefik protégée

Remplacez la situation vulnérable sur `edge.lab` par un accès
d'administration HTTPS sur `admin.lab.test`.

### Critères

- le port direct 8080 n'écoute plus sur l'hôte ;
- sans identifiants, le tableau de bord et l'API répondent HTTP 401 en HTTPS ;
- avec les identifiants fournis, les deux répondent HTTP 200 ;
- le client valide le certificat de test pour `admin.lab.test` ;
- Traefik utilise le proxy de socket Docker épinglé, sans montage direct du
  socket ;
- les réponses portent les en-têtes de sécurité et une rafale authentifiée
  déclenche HTTP 429.

Les tests observent le comportement réel du port et des routes, le montage du
socket Docker, les en-têtes HTTP et la réponse sous charge ; ils ne vérifient
pas un fichier Compose précis.
