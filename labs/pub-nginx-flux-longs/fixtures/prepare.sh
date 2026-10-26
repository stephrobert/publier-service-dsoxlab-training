#!/usr/bin/env bash
# Pose la situation : trois transports longs derriere un proxy qui les
# traite comme des pages.
#
# LES QUATRE DEFAUTS POSES
#   1. pas de `Upgrade`/`Connection` transmis : le WebSocket n'etablit
#      jamais sa poignee de main ;
#   2. `proxy_buffering on` : les evenements SSE arrivent tous ensemble a
#      la fin, au lieu d'un par seconde ;
#   3. pas de `grpc_pass` : gRPC passe par un proxy HTTP/1 et echoue ;
#   4. `proxy_read_timeout 10s` : un flux long est coupe en pleine
#      conversation.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-nginx-flux-longs.log) 2>&1
set -x

WORK=/opt/pub-nginx-flux-longs

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends curl python3-grpcio

rm -f /etc/nginx/conf.d/default.conf
install -d -m 0775 -o student -g student "$WORK"
find "$WORK" -mindepth 1 -delete
install -o student -g student -m 0644 /tmp/pub-flux-backends.py "$WORK/backends.py"

cat > /etc/systemd/system/pub-nginx-flux-backends.service <<'UNIT'
[Unit]
Description=WebSocket, SSE and gRPC backends for the Nginx long-streams lab
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/pub-nginx-flux-longs/backends.py
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now pub-nginx-flux-backends.service

cat > /etc/nginx/conf.d/flux.conf <<'CONF'
server {
    listen 80 default_server;
    # gRPC exige HTTP/2. Sans cette ligne, le proxy parle HTTP/1 a un
    # client qui parle HTTP/2, et rien n'aboutit.
    server_name flux.lab.test;

    # Dix secondes : un flux long est coupe en pleine conversation.
    proxy_read_timeout 10s;
    proxy_send_timeout 10s;

    location /ws {
        proxy_pass http://127.0.0.1:18101;
        proxy_http_version 1.1;
        # Ni Upgrade ni Connection : la poignee de main n'aboutit jamais.
        proxy_set_header Host $host;
    }

    location /sse {
        proxy_pass http://127.0.0.1:18102;
        # La mise en tampon retient les evenements et les livre ensemble.
        proxy_buffering on;
        proxy_set_header Host $host;
    }

    location /essai.Echo/ {
        # Un proxy HTTP ordinaire devant un service gRPC : il ne passera
        # pas.
        proxy_pass http://127.0.0.1:18103;
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://127.0.0.1:18102;
        proxy_set_header Host $host;
    }
}
CONF

cat > "$WORK/transports.txt" <<'TXT'
Les trois transports du banc, et ce qu'ils attendent du proxy.

  /ws              WebSocket. Le backend renvoie « echo:<ce qu'il recoit> ».
                   Il faut que la poignee de main aboutisse ET que les
                   trames circulent ensuite dans les deux sens.

  /sse             Six evenements, UN PAR SECONDE. Le proxy ne doit pas les
                   retenir : livres tous ensemble a la fin, ils sont
                   inutilisables, et pourtant tous presents.

  /essai.Echo/Dire gRPC, en clair (h2c). La charge « erreur » declenche un
                   refus APPLICATIF, qui doit arriver au client comme tel et
                   non comme une panne de transport.

  port 18104       le port d'ecoute attendu pour gRPC, en HTTP/2 sans TLS.

Le client dispose de /usr/local/bin/client-grpc, qui imprime « ok »,
« erreur » ou « transport » selon ce qu'il observe.
TXT
chown student:student "$WORK/transports.txt"
chmod 0644 "$WORK/transports.txt"

nginx -t
systemctl enable --now nginx
systemctl reload nginx

for _ in $(seq 1 20); do
  if curl --max-time 3 --silent --output /dev/null http://127.0.0.1/; then
    echo "Situation posée : trois transports longs, traités comme des pages."
    exit 0
  fi
  sleep 1
done
echo "Nginx ne répond pas." >&2
exit 1
