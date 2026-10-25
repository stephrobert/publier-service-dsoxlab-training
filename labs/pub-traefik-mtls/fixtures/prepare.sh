#!/usr/bin/env bash
# Pose la situation : une CA client, une CA backend, des certificats valides
# et des variantes invalides, deux backends (bon/mauvais certificat), un
# reverse proxy amont autorisé, et un Traefik dont le mTLS, la vérification
# du backend et la confiance accordée aux en-têtes transférés sont
# partiellement mal réglés.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-mtls.log) 2>&1
set -x

WORK=/opt/pub-mtls

for port in 8443 8080; do
  if timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "Le port $port est déjà occupé avant la mise en situation." >&2
    exit 1
  fi
done

docker rm -f pub-mtls-traefik pub-mtls-backend-bon pub-mtls-backend-mauvais \
  pub-mtls-nginx-amont 2>/dev/null || true
docker network rm pub-mtls 2>/dev/null || true

install -d -m 0775 -o student -g docker "$WORK"
find "$WORK" -mindepth 1 -delete
install -d -m 0775 -o student -g docker "$WORK/dynamic" "$WORK/certs" "$WORK/nginx"

docker pull "$IMG_TRAEFIK"
docker pull "$IMG_WHOAMI"
docker pull "$IMG_NGINX"

docker network create --subnet 172.30.10.0/24 pub-mtls

CERTS="$WORK/certs"

# --- CA client (autorité légitime pour les certificats clients) ---
openssl genrsa -out "$CERTS/client-ca.key" 2048
openssl req -x509 -new -nodes -key "$CERTS/client-ca.key" -sha256 -days 30 \
  -subj '/CN=pub-mtls Client CA' -out "$CERTS/client-ca.crt"

# --- CA étrangère (pour simuler un certificat client refusé) ---
openssl genrsa -out "$CERTS/etrangere-ca.key" 2048
openssl req -x509 -new -nodes -key "$CERTS/etrangere-ca.key" -sha256 -days 30 \
  -subj '/CN=Etrangere CA' -out "$CERTS/etrangere-ca.crt"

# --- CA backend (autorité légitime pour le certificat du backend) ---
openssl genrsa -out "$CERTS/backend-ca.key" 2048
openssl req -x509 -new -nodes -key "$CERTS/backend-ca.key" -sha256 -days 30 \
  -subj '/CN=pub-mtls Backend CA' -out "$CERTS/backend-ca.crt"

# --- CA mauvaise (pour simuler un certificat backend refusé) ---
openssl genrsa -out "$CERTS/mauvaise-ca.key" 2048
openssl req -x509 -new -nodes -key "$CERTS/mauvaise-ca.key" -sha256 -days 30 \
  -subj '/CN=Mauvaise CA' -out "$CERTS/mauvaise-ca.crt"

sign_client() {
  local nom="$1" ca_key="$2" ca_crt="$3"
  openssl genrsa -out "$CERTS/$nom.key" 2048
  openssl req -new -key "$CERTS/$nom.key" -subj "/CN=$nom" \
    -out "$CERTS/$nom.csr"
  openssl x509 -req -in "$CERTS/$nom.csr" -CA "$ca_crt" -CAkey "$ca_key" \
    -CAcreateserial -days 30 -sha256 \
    -out "$CERTS/$nom.crt"
  rm -f "$CERTS/$nom.csr"
}

sign_client_expire() {
  # openssl x509 -req ne sait pas poser des dates explicites : on passe par
  # une mini-autorité "openssl ca" pour émettre un certificat déjà expiré.
  local nom="$1"
  local ca_dir="$CERTS/ca-expire"
  install -d -m 0700 "$ca_dir/newcerts"
  touch "$ca_dir/index.txt"
  echo 1000 > "$ca_dir/serial"
  cat > "$ca_dir/openssl.cnf" <<CNF
[ca]
default_ca = defaut
[defaut]
dir = $ca_dir
database = $ca_dir/index.txt
new_certs_dir = $ca_dir/newcerts
serial = $ca_dir/serial
certificate = $CERTS/client-ca.crt
private_key = $CERTS/client-ca.key
default_md = sha256
policy = policy_any
[policy_any]
commonName = supplied
CNF
  openssl genrsa -out "$CERTS/$nom.key" 2048
  openssl req -new -key "$CERTS/$nom.key" -subj "/CN=$nom" \
    -out "$CERTS/$nom.csr"
  openssl ca -batch -config "$ca_dir/openssl.cnf" \
    -startdate "$(date -u -d '-60 days' +%y%m%d%H%M%SZ)" \
    -enddate "$(date -u -d '-1 day' +%y%m%d%H%M%SZ)" \
    -in "$CERTS/$nom.csr" -out "$CERTS/$nom.crt"
  rm -f "$CERTS/$nom.csr"
  rm -rf "$ca_dir"
}

sign_client client-valide "$CERTS/client-ca.key" "$CERTS/client-ca.crt"
sign_client client-etranger "$CERTS/etrangere-ca.key" \
  "$CERTS/etrangere-ca.crt"
sign_client_expire client-expire
sign_client nginx-amont "$CERTS/client-ca.key" "$CERTS/client-ca.crt"

sign_backend() {
  local nom="$1" ca_key="$2" ca_crt="$3"
  openssl genrsa -out "$CERTS/$nom.key" 2048
  openssl req -new -key "$CERTS/$nom.key" -subj "/CN=$nom" \
    -out "$CERTS/$nom.csr"
  openssl x509 -req -in "$CERTS/$nom.csr" -CA "$ca_crt" -CAkey "$ca_key" \
    -CAcreateserial -days 30 -sha256 \
    -extfile <(printf 'subjectAltName=DNS:%s' "$nom") \
    -out "$CERTS/$nom.crt"
  rm -f "$CERTS/$nom.csr"
}


sign_backend backend-bon "$CERTS/backend-ca.key" "$CERTS/backend-ca.crt"
sign_backend backend-mauvais "$CERTS/mauvaise-ca.key" "$CERTS/mauvaise-ca.crt"

# --- Certificat de service de Traefik lui-même (non vérifié par les tests) ---
openssl genrsa -out "$CERTS/edge-server.key" 2048
openssl req -x509 -new -nodes -key "$CERTS/edge-server.key" -sha256 -days 30 \
  -subj '/CN=mtls.lab.test' -addext 'subjectAltName=DNS:mtls.lab.test' \
  -out "$CERTS/edge-server.crt"

chmod 0644 "$CERTS"/*.crt "$CERTS"/*.key
chown -R student:docker "$WORK"

docker run -d --name pub-mtls-backend-bon --network pub-mtls \
  --hostname backend-bon \
  -v "$CERTS/backend-bon.crt:/certs/tls.crt:ro" \
  -v "$CERTS/backend-bon.key:/certs/tls.key:ro" \
  "$IMG_WHOAMI" -port 8080 -cert /certs/tls.crt -key /certs/tls.key -name bon

docker run -d --name pub-mtls-backend-mauvais --network pub-mtls \
  --hostname backend-mauvais \
  -v "$CERTS/backend-mauvais.crt:/certs/tls.crt:ro" \
  -v "$CERTS/backend-mauvais.key:/certs/tls.key:ro" \
  "$IMG_WHOAMI" -port 8080 -cert /certs/tls.crt -key /certs/tls.key -name mauvais

# --- Configuration dynamique initiale : partiellement mal réglée ---
cat > "$WORK/dynamic/routes.yaml" <<'YAML'
tls:
  options:
    mtls:
      clientAuth:
        caFiles:
          - /etc/traefik/certs/client-ca.crt
        clientAuthType: NoClientCert
  stores:
    default:
      defaultCertificate:
        certFile: /etc/traefik/certs/edge-server.crt
        keyFile: /etc/traefik/certs/edge-server.key
  certificates:
    - certFile: /etc/traefik/certs/edge-server.crt
      keyFile: /etc/traefik/certs/edge-server.key

http:
  serversTransports:
    verif-backend:
      insecureSkipVerify: true
  routers:
    bon:
      rule: Host(`bon.mtls.lab.test`)
      entryPoints:
        - websecure
      tls:
        options: mtls@file
      service: bon
    mauvais:
      rule: Host(`mauvais.mtls.lab.test`)
      entryPoints:
        - websecure
      tls:
        options: mtls@file
      service: mauvais
  services:
    bon:
      loadBalancer:
        serversTransport: verif-backend
        servers:
          - url: https://backend-bon:8080
    mauvais:
      loadBalancer:
        serversTransport: verif-backend
        servers:
          - url: https://backend-mauvais:8080
YAML

cat > "$WORK/traefik-static.yaml" <<'YAML'
entryPoints:
  websecure:
    address: ":8443"
    forwardedHeaders:
      trustedIPs:
        - "0.0.0.0/0"
providers:
  file:
    directory: /etc/traefik/dynamic
    watch: true
log:
  level: INFO
YAML

docker run -d --name pub-mtls-traefik \
  --network pub-mtls \
  --hostname traefik \
  --ip 172.30.10.5 \
  -p 8443:8443 \
  -v "$WORK/traefik-static.yaml:/etc/traefik/traefik.yaml:ro" \
  -v "$WORK/dynamic:/etc/traefik/dynamic:ro" \
  -v "$CERTS:/etc/traefik/certs:ro" \
  "$IMG_TRAEFIK" --configfile=/etc/traefik/traefik.yaml

# --- Reverse proxy amont autorisé : termine la connexion cliente en clair,
# ajoute X-Forwarded-For, puis se présente à Traefik avec SON PROPRE
# certificat client valide. ---
cat > "$WORK/nginx/nginx.conf" <<'CONF'
events {}
http {
  server {
    listen 8080;
    location / {
      proxy_pass https://traefik:8443;
      proxy_ssl_certificate /certs/nginx-amont.crt;
      proxy_ssl_certificate_key /certs/nginx-amont.key;
      proxy_ssl_verify off;
      proxy_ssl_server_name on;
      proxy_ssl_name $http_host;
      proxy_set_header Host $http_host;
      proxy_set_header X-Forwarded-For $remote_addr;
    }
  }
}
CONF

docker run -d --name pub-mtls-nginx-amont \
  --network pub-mtls \
  --ip 172.30.10.10 \
  -p 8080:8080 \
  -v "$WORK/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$CERTS:/certs:ro" \
  "$IMG_NGINX"

for _ in $(seq 1 30); do
  if curl --max-time 2 --silent --output /dev/null -k \
    --cert "$CERTS/client-valide.crt" --key "$CERTS/client-valide.key" \
    -H 'Host: bon.mtls.lab.test' https://127.0.0.1:8443/ 2>/dev/null; then
    break
  fi
  sleep 1
done

cat > "$WORK/README" <<'TXT'
Répertoire de travail du lab pub-traefik-mtls.

Traefik lit sa configuration dynamique dans /opt/pub-mtls/dynamic/routes.yaml
(options TLS « mtls », transport serveur « verif-backend », routeurs « bon »
et « mauvais ») et sa configuration statique dans
/opt/pub-mtls/traefik-static.yaml (point d'entrée « websecure » sur le port
8443, confiance accordée aux en-têtes transférés).

Les certificats préparés sont dans /opt/pub-mtls/certs/ :
  - client-ca.crt / client-ca.key : l'autorité cliente légitime du lab ;
  - client-valide.{crt,key} : un certificat client valide signé par elle ;
  - client-etranger.{crt,key} : un certificat signé par une autre CA ;
  - client-expire.{crt,key} : un certificat signé par la bonne CA mais déjà
    expiré ;
  - backend-ca.crt / backend-ca.key : l'autorité backend légitime du lab ;
  - backend-bon sert son certificat signé par backend-ca ;
  - backend-mauvais sert un certificat signé par une autre CA
    (mauvaise-ca.crt), joignable via le routeur « mauvais » ;
  - nginx-amont.{crt,key} : le certificat client du reverse proxy amont
    autorisé, qui écoute en clair sur le port 8080 et relaie vers Traefik
    avec ce certificat.

La configuration actuelle est mal réglée :
  - l'option TLS « mtls » référence la CA cliente mais clientAuthType vaut
    NoClientCert : aucun certificat n'est en fait exigé ;
  - le transport serveur « verif-backend » a insecureSkipVerify à true : la
    connexion vers backend-mauvais n'échoue pas alors qu'elle le devrait ;
  - le point d'entrée fait confiance aux en-têtes transférés de n'importe
    quelle adresse (0.0.0.0/0), donc un appelant direct peut forger
    X-Forwarded-For.

Corrigez /opt/pub-mtls/dynamic/routes.yaml et
/opt/pub-mtls/traefik-static.yaml (ce dernier impose un redémarrage du
conteneur pub-mtls-traefik : « docker restart pub-mtls-traefik »). Les tests
appellent le véritable point d'entrée HTTPS sur le port 8443 (clients
directs) et le reverse proxy amont sur le port 8080 (clients indirects).
TXT
chown -R student:docker "$WORK"
echo "Situation posée : CA et certificats prêts, deux backends actifs, Traefik mal réglé en trois points."
