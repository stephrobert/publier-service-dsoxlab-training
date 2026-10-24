"""Verify real Traefik access logs and Prometheus observations."""

from __future__ import annotations

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
HOTE = "observabilite.lab.test"


def test_journaux_json_filtrent_les_reponses_5xx() -> None:
    edge = lab_host(CIBLE)
    response = edge.run(
        "curl --max-time 5 --silent --show-error --output /dev/null "
        f"-H 'Host: {HOTE}' http://127.0.0.1/ && "
        "curl --max-time 5 --silent --show-error --output /dev/null "
        "--write-out '%{http_code}' "
        f"-H 'Host: {HOTE}' http://127.0.0.1/fail"
    )
    assert response.rc == 0 and response.stdout.strip() == "503", message(
        en="The controlled backend path must return a real HTTP 503 response.",
        fr="Le chemin backend de contrôle doit réellement répondre HTTP 503.",
    )

    result = edge.run(
        "python3 -c 'import json,pathlib,sys; "
        "p=pathlib.Path(\"/opt/pub-observabilite/logs/access.json\"); "
        "rows=[json.loads(line) for line in p.read_text().splitlines() if line]; "
        "ok=bool(rows) and all(500 <= int(row[\"DownstreamStatus\"]) < 600 "
        "and row.get(\"RequestHost\")==\"observabilite.lab.test\" "
        "and row.get(\"RequestPath\")==\"/fail\" "
        "and not any(key.lower().startswith(\"requestheader\") for key in row) "
        "for row in rows); print(\"ok\" if ok else \"invalid\")'"
    )
    assert result.rc == 0 and result.stdout.strip() == "ok", message(
        en="The JSON access log must contain the 5xx request with its host, "
        "path, and status, and must omit request-header fields.",
        fr="Le journal d'accès JSON doit contenir la requête 5xx avec son hôte, "
        "son chemin et son statut, sans champ d'en-tête de requête.",
    )


def test_cible_traefik_est_up_dans_prometheus() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "python3 -c 'import json,time,urllib.request; "
        "url=\"http://127.0.0.1:9090/api/v1/targets?state=active\"; "
        "ok=False; "
        "forbidden=False; "
        "exec(\"for _ in range(25):\\n"
        " try:\\n"
        "  data=json.load(urllib.request.urlopen(url,timeout=2))[\\\"data\\\"][\\\"activeTargets\\\"]\\n"
        "  ok=any(t[\\\"labels\\\"].get(\\\"job\\\")==\\\"traefik\\\" and t[\\\"health\\\"]==\\\"up\\\" and \\\"127.0.0.1:8082\\\" in t[\\\"scrapeUrl\\\"] for t in data)\\n"
        "  if ok: break\\n"
        " except Exception: pass\\n"
        " time.sleep(1)\"); print(\"up\" if ok else \"down\")'"
    )
    assert result.rc == 0 and result.stdout.strip() == "up", message(
        en="Prometheus must report the Traefik scrape target at "
        "127.0.0.1:8082 as up.",
        fr="Prometheus doit déclarer active la cible Traefik "
        "127.0.0.1:8082.",
    )


def test_endpoints_de_supervision_restent_locaux() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "python3 -c 'import json,subprocess; "
        "traefik=json.loads(subprocess.check_output([\"docker\",\"inspect\",\"-f\",\"{{json .Config.Cmd}}\",\"pub-observabilite-traefik\"],text=True)); "
        "prometheus=json.loads(subprocess.check_output([\"docker\",\"inspect\",\"-f\",\"{{json .Config.Cmd}}\",\"pub-observabilite-prometheus\"],text=True)); "
        "print(\"ok\" if \"--entrypoints.metrics.address=127.0.0.1:8082\" in traefik and \"--web.listen-address=127.0.0.1:9090\" in prometheus else \"exposed\")'"
    )
    assert result.rc == 0 and result.stdout.strip() == "ok", message(
        en="Traefik metrics and the Prometheus API must both bind to loopback.",
        fr="Les métriques Traefik et l'API Prometheus doivent rester liées à "
        "l'interface de boucle locale.",
    )


def test_alerte_5xx_passe_a_firing_apres_une_erreur_reelle() -> None:
    edge = lab_host(CIBLE)
    result = edge.run(
        "python3 -c 'exec(\"\"\""
        "import json,time,urllib.request,urllib.error\n"
        f"request=urllib.request.Request(\"http://127.0.0.1/fail\",headers={{\"Host\":\"{HOTE}\"}})\n"
        "try:\n"
        " status=urllib.request.urlopen(request,timeout=5).status\n"
        "except urllib.error.HTTPError as error:\n"
        " status=error.code\n"
        "alerts_url=\"http://127.0.0.1:9090/api/v1/alerts\"\n"
        "rules_url=\"http://127.0.0.1:9090/api/v1/rules\"\n"
        "firing=False\n"
        "for _ in range(25):\n"
        " try:\n"
        "  alerts=json.load(urllib.request.urlopen(alerts_url,timeout=2))[\"data\"][\"alerts\"]\n"
        "  groups=json.load(urllib.request.urlopen(rules_url,timeout=2))[\"data\"][\"groups\"]\n"
        "  is_5xx=any(\"5..\" in rule.get(\"query\",\"\") and \"traefik_\" in rule.get(\"query\",\"\") for group in groups for rule in group[\"rules\"] if rule.get(\"type\")==\"alerting\")\n"
        "  firing=any(alert[\"state\"]==\"firing\" for alert in alerts) and is_5xx\n"
        "  if firing:\n"
        "   break\n"
        " except Exception:\n"
        "  pass\n"
        " time.sleep(1)\n"
        "print(\"firing\" if status==503 and firing else \"not-firing\")\n"
        "\"\"\")'"
    )
    assert result.rc == 0 and result.stdout.strip() == "firing", message(
        en="A real backend HTTP 503 response must cause a configured Prometheus "
        "alert to enter the firing state.",
        fr="Une véritable réponse HTTP 503 du backend doit déclencher une "
        "alerte Prometheus à l'état firing.",
    )
