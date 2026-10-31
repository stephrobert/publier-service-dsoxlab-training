#!/usr/bin/env bash
# Injecte l'incident tiré au sort par prepare.sh, UNE SEULE FOIS, quand
# l'apprenant a signalé sa recette initiale (écriture de
# /home/student/recette-initiale.md, surveillée par pub-epn-incident.path).
#
# Il agit sur ce qui existe quelle que soit la façon dont l'apprenant a
# écrit sa configuration : le processus du backend, ses droits sur le
# contenu, le certificat que `nginx -T` désigne, le comportement du backend
# redéployé. Il ne réécrit jamais la configuration de Nginx.
set -euo pipefail

SECRET=/root/.pub-epn-secret.yaml
CACHE=/root/.pub-epn
STATE=/var/lib/pub-epn
WORK=/opt/pub-epreuve-nginx
DRAPEAU="$STATE/incident-injecte"

[ -e "$DRAPEAU" ] && exit 0

# Laisse à l'apprenant le temps de fermer son éditeur et de lancer sa
# dernière vérification : l'incident arrive APRÈS la recette, pas pendant.
sleep 5

INCIDENT=$(awk '/^incident:/{print $2; exit}' "$SECRET")

case "$INCIDENT" in
  amont)
    # Un redéploiement du backend l'a déplacé sur un autre port.
    install -d /etc/systemd/system/pub-epn-api.service.d
    cat > /etc/systemd/system/pub-epn-api.service.d/redeploiement.conf <<'CONF'
[Service]
Environment=PORT=18299
CONF
    systemctl daemon-reload
    systemctl restart pub-epn-api.service
    ;;
  tls)
    # Le certificat servi est remplacé par un certificat périmé. Les
    # chemins viennent de la configuration réellement chargée.
    for _ in $(seq 1 30); do
      if nginx -T 2>/dev/null | awk '$1=="ssl_certificate"{f=1} END{exit !f}'; then
        break
      fi
      sleep 2
    done
    nginx -T 2>/dev/null \
      | awk '$1=="ssl_certificate"||$1=="ssl_certificate_key"{gsub(/[;"]/,"",$2); print $1" "$2}' \
      | sort -u > "$CACHE/chemins-tls.txt"
    while read -r directive chemin; do
      [ -n "$chemin" ] || continue
      if [ "$directive" = ssl_certificate ]; then
        cat "$CACHE/expire.crt" > "$chemin"
      else
        cat "$CACHE/expire.key" > "$chemin"
      fi
    done < "$CACHE/chemins-tls.txt"
    systemctl reload nginx.service || systemctl restart nginx.service
    ;;
  droits)
    # Une livraison de contenu a refermé le répertoire du site.
    chown -R root:root "$WORK/site"
    chmod 0700 "$WORK/site"
    ;;
  entetes)
    # Le backend redéployé n'accepte plus que son nom public dans Host.
    touch "$STATE/exige-host"
    ;;
esac

date -u +%FT%TZ > "$DRAPEAU"
