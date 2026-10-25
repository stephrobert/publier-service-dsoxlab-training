# Défi : administration Traefik protégée

Remplacez la situation vulnérable sur `edge.lab` par un accès
d'administration HTTPS sur `admin.lab.test`.

## Critères

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
