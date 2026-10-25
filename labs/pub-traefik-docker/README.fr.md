# pub-traefik-docker

Publier deux instances d'un service web derrière Traefik avec le fournisseur
Docker : découverte par étiquettes, rien d'exposé par défaut, aucun port de
backend publié, et une instance qui peut tomber avec basculement mesuré selon
les seuils du défi. Guide :
https://www.stephane-robert.info/docs/services/reseau/traefik-docker/

```bash
dsoxlab run pub-traefik-docker
dsoxlab check pub-traefik-docker
```
