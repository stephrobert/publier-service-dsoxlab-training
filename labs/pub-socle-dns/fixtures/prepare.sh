#!/usr/bin/env bash
# Pose la situation sur edge.lab : une zone `pub.test` servie par bind9, un
# résolveur à cache (unbound) devant elle, et deux versions du site sur deux
# adresses IPv4 et deux adresses IPv6.
set -euo pipefail
exec > >(tee /var/log/dsoxlab-pub-socle-dns.log) 2>&1
set -x

STATE=/var/lib/pub-dns
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq bind9 unbound dnsutils >/dev/null

IFACE=$(ip -4 route show default | awk '{print $5; exit}')
EDGE_IP=$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | cut -d/ -f1 | head -1)
BASE=${EDGE_IP%.*}
V1_4=$BASE.201
V2_4=$BASE.202
V1_6=fd77:1::201
V2_6=fd77:1::202

for a in "$V1_4/24" "$V2_4/24" "$V1_6/64" "$V2_6/64"; do
  ip addr replace "$a" dev "$IFACE"
done
# bind ne s'attache qu'aux adresses portées par une interface.
ip addr replace 127.0.0.2/8 dev lo

install -d -m 0755 /opt/pub-dns
install -m 0644 /tmp/pub-socle-backend.py /opt/pub-dns/backend.py
rm -rf "$STATE"
install -d -m 0750 "$STATE"

TOKEN=$(head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n')
TTL=$(shuf -i 900-3600 -n 1)

for v in v1 v2; do
  a4=$V1_4; a6=$V1_6
  if [ "$v" = v2 ]; then a4=$V2_4; a6=$V2_6; fi
  cat > /etc/systemd/system/pub-dns-$v.service <<UNIT
[Unit]
Description=Site $v (lab DNS)
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/pub-dns/backend.py $v $TOKEN $a4 $a6
Restart=on-failure
UNIT
done

cat > /etc/bind/pub.test.zone <<ZONE
\$TTL $TTL
@    IN SOA ns.pub.test. admin.pub.test. ( 2026102501 3600 600 86400 $TTL )
@    IN NS  ns.pub.test.
ns   IN A   127.0.0.2
shop IN A    $V1_4
shop IN AAAA $V1_6
www  IN CNAME shop
ZONE
chown root:bind /etc/bind/pub.test.zone
chmod 0664 /etc/bind/pub.test.zone

cat > /etc/bind/named.conf.options <<CONF
options {
  directory "/var/cache/bind";
  listen-on { 127.0.0.2; };
  listen-on-v6 { none; };
  recursion no;
  allow-query { 127.0.0.0/8; };
  dnssec-validation no;
};
CONF
cat > /etc/bind/named.conf.local <<CONF
zone "pub.test" { type primary; file "/etc/bind/pub.test.zone"; };
CONF

cat > /etc/unbound/unbound.conf.d/pub.conf <<CONF
server:
  interface: $EDGE_IP
  interface: 127.0.0.1
  access-control: 127.0.0.0/8 allow
  access-control: $BASE.0/24 allow
  do-not-query-localhost: no
  domain-insecure: "pub.test"
  private-domain: "pub.test"
  local-zone: "test." nodefault
remote-control:
  control-enable: yes
  control-interface: /run/unbound.ctl
  control-use-cert: no
forward-zone:
  name: "pub.test."
  forward-addr: 127.0.0.2
CONF
rm -f /etc/unbound/unbound.conf.d/remote-control.conf

systemctl daemon-reload
systemctl restart named pub-dns-v1 pub-dns-v2
for _ in 1 2 3 4 5; do
  systemctl restart unbound && break
  sleep 2
done
systemctl is-active --quiet unbound

for _ in $(seq 1 30); do
  dig +short @127.0.0.2 shop.pub.test A | grep -q . && break
  sleep 1
done

# Le cache du résolveur est amorcé avec l'ancienne réponse.
dig +short @"$EDGE_IP" shop.pub.test A >/dev/null
dig +short @"$EDGE_IP" shop.pub.test AAAA >/dev/null

cat > "$STATE/etat.json" <<JSON
{"token": "$TOKEN", "ttl": $TTL, "edge_ip": "$EDGE_IP", "v1_4": "$V1_4", "v2_4": "$V2_4", "v1_6": "$V1_6", "v2_6": "$V2_6"}
JSON

cat > /home/student/README-dns <<TXT
Le site shop.pub.test tourne en version v1 et doit passer en version v2.

Serveur qui fait autorité sur la zone pub.test : 127.0.0.2 (fichier de zone /etc/bind/pub.test.zone,
service named, rechargement avec : sudo rndc reload)
Résolveur à cache : $EDGE_IP (service unbound, cache vidé avec : sudo unbound-control flush_zone pub.test)
Version v1 : $V1_4 et $V1_6
Version v2 : $V2_4 et $V2_6

Le poste.lab interroge le résolveur $EDGE_IP pour tous les noms en pub.test.
TXT
chown student:student /home/student/README-dns
