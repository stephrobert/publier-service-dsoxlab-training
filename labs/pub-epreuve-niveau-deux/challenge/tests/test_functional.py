"""Assess protection, observability, and diagnosis of an unknown outage."""

from __future__ import annotations

from conftest import lab_host, lab_target_host, message

CIBLE = lab_target_host("edge.lab")
WORK = "/opt/pub-epreuve-niveau-deux"
HOTE_APP = "app.lab.test"
HOTE_ADMIN = "admin.lab.test"
IDENTIFIANT = "operator:E2-Observe-2026"
DELAI_EPREUVE_S = 75 * 60


def _edge():
    return lab_host(CIBLE)


def _dans_le_delai(edge) -> bool:
    result = edge.run(
        "python3 -c 'import pathlib,time; "
        f"start=int(pathlib.Path(\"{WORK}/assessment-started-at\").read_text()); "
        "print(int(time.time())-start)'"
    )
    return result.rc == 0 and result.stdout.strip().isdigit() and int(
        result.stdout.strip()
    ) <= DELAI_EPREUVE_S


def test_panne_inconnue_reparee_et_diagnostic_documente() -> None:
    edge = _edge()
    response = edge.run(
        "curl --max-time 5 --silent --show-error --insecure "
        "--resolve app.lab.test:443:127.0.0.1 "
        "--dump-header /tmp/e2-app-headers "
        "--output /tmp/e2-app-body --write-out '%{http_code}' "
        "https://app.lab.test/"
    )
    body = edge.run("cat /tmp/e2-app-body")
    report = edge.run(
        f"python3 -c 'from pathlib import Path; "
        f"p=Path(\"{WORK}/incident-report.txt\"); "
        "print(p.read_text() if p.is_file() else \"\")'"
    )
    contenu = report.stdout.lower()
    assert (
        _dans_le_delai(edge)
        and response.rc == 0
        and response.stdout.strip() == "200"
        and "E2 backend" in body.stdout
        and report.rc == 0
        and len(contenu) >= 100
        and all(token in contenu for token in ("502", "18088", "18087", "200"))
    ), message(
        en="Restore app.lab.test to HTTP 200 and document the 502 symptom, "
        "log evidence, root cause, correction, and successful response in "
        "incident-report.txt.",
        fr="Rétablissez app.lab.test en HTTP 200 et consignez dans "
        "incident-report.txt le symptôme 502, la preuve des journaux, la cause, "
        "la correction et la réponse obtenue.",
    )


def test_administration_https_exige_une_authentification() -> None:
    edge = _edge()
    unauthenticated = edge.run(
        "curl --max-time 5 --silent --show-error --insecure "
        "--resolve admin.lab.test:443:127.0.0.1 --output /dev/null "
        "--write-out '%{http_code}' https://admin.lab.test/dashboard/"
    )
    authenticated = edge.run(
        "curl --max-time 5 --silent --show-error --insecure "
        "--resolve admin.lab.test:443:127.0.0.1 "
        f"--user '{IDENTIFIANT}' --output /dev/null "
        "--write-out '%{http_code}' https://admin.lab.test/dashboard/"
    )
    assert (
        _dans_le_delai(edge)
        and unauthenticated.rc == 0
        and unauthenticated.stdout.strip() == "401"
        and authenticated.rc == 0
        and authenticated.stdout.strip() == "200"
    ), message(
        en="The HTTPS dashboard must return 401 without credentials and 200 "
        "for the supplied operator account.",
        fr="Le tableau de bord HTTPS doit répondre 401 sans identifiants et "
        "200 avec le compte opérateur fourni.",
    )


def test_entetes_de_securite_et_endpoint_admin_non_expose() -> None:
    edge = _edge()
    response = edge.run(
        "curl --max-time 5 --silent --show-error --insecure "
        "--resolve app.lab.test:443:127.0.0.1 --dump-header /tmp/e2-headers "
        "--output /dev/null --write-out '%{http_code}' "
        "https://app.lab.test/ && "
        "tr -d '\\r' < /tmp/e2-headers | "
        "grep -Eiq '^x-content-type-options: nosniff$' && "
        "tr -d '\\r' < /tmp/e2-headers | "
        "grep -Eiq '^x-frame-options: DENY$' && "
        "tr -d '\\r' < /tmp/e2-headers | "
        "grep -Eiq '^referrer-policy: no-referrer$' && "
        "! ss -ltnH 'sport = :8080' | grep -q ."
    )
    assert (
        _dans_le_delai(edge)
        and response.rc == 0
        and response.stdout.strip() == "200"
    ), message(
        en="Application responses must carry the required security headers, "
        "and the unauthenticated dashboard port 8080 must not listen.",
        fr="Les réponses de l'application doivent porter les en-têtes requis "
        "et le port 8080 du tableau de bord ne doit pas écouter sans "
        "authentification.",
    )


def test_une_rafale_est_limitee_par_traefik() -> None:
    edge = _edge()
    result = edge.run(
        "seq 1 16 | xargs -P 16 -I{} curl --max-time 5 --silent "
        "--show-error --insecure --output /dev/null --write-out '%{http_code}\\n' "
        "--resolve admin.lab.test:443:127.0.0.1 "
        f"--user '{IDENTIFIANT}' https://admin.lab.test/api/overview"
    )
    codes = result.stdout.splitlines()
    assert _dans_le_delai(edge) and result.rc == 0 and "429" in codes, message(
        en=f"A burst of authenticated requests did not trigger HTTP 429 "
        f"(curl rc={result.rc}, observed codes={codes!r}).",
        fr=f"Une rafale de requêtes authentifiées n'a pas déclenché HTTP 429 "
        f"(curl rc={result.rc}, codes observés={codes!r}).",
    )


def test_journal_json_filtre_les_5xx_et_omet_les_entetes() -> None:
    edge = _edge()
    response = edge.run(
        "curl --max-time 5 --silent --show-error --insecure "
        "--resolve app.lab.test:443:127.0.0.1 --output /dev/null "
        "--write-out '%{http_code}' https://app.lab.test/incident"
    )
    log = edge.run(
        "python3 -c 'import json,pathlib; "
        f"p=pathlib.Path(\"{WORK}/logs/access.json\"); "
        "rows=[json.loads(line) for line in p.read_text().splitlines() if line]; "
        "matching=[row for row in rows if row.get(\"RequestPath\")==\"/incident\"]; "
        "ok=bool(matching) and all(500 <= int(row[\"DownstreamStatus\"]) < 600 "
        "and row.get(\"RequestHost\")==\"app.lab.test\" "
        "and not any(key.lower().startswith(\"requestheader\") for key in row) "
        "for row in rows); print(\"ok\" if ok else \"invalid\")'"
    )
    assert (
        _dans_le_delai(edge)
        and response.rc == 0
        and response.stdout.strip() == "503"
        and log.rc == 0
        and log.stdout.strip() == "ok"
    ), message(
        en="A real 503 must appear in JSON access logs with its host and path; "
        "all retained entries must be 5xx and request headers must be dropped.",
        fr="Un véritable 503 doit apparaître dans les journaux JSON avec son "
        "hôte et son chemin ; les entrées conservées doivent être des 5xx et "
        "les en-têtes de requête doivent être omis.",
    )


def test_prometheus_observe_traefik_et_declenche_l_alerte_5xx() -> None:
    edge = _edge()
    result = edge.run(
        "python3 -c 'exec(\"\"\""
        "import json,time,urllib.request,urllib.error\\n"
        f"request=urllib.request.Request(\"https://127.0.0.1/incident\",headers={{\"Host\":\"{HOTE_APP}\"}})\\n"
        "try:\\n"
        " status=urllib.request.urlopen(request,context=__import__(\"ssl\")._create_unverified_context(),timeout=5).status\\n"
        "except urllib.error.HTTPError as error:\\n"
        " status=error.code\\n"
        "targets_url=\"http://127.0.0.1:9090/api/v1/targets?state=active\"\\n"
        "alerts_url=\"http://127.0.0.1:9090/api/v1/alerts\"\\n"
        "rules_url=\"http://127.0.0.1:9090/api/v1/rules\"\\n"
        "ready=False\\n"
        "for _ in range(30):\\n"
        " try:\\n"
        "  targets=json.load(urllib.request.urlopen(targets_url,timeout=2))[\"data\"][\"activeTargets\"]\\n"
        "  groups=json.load(urllib.request.urlopen(rules_url,timeout=2))[\"data\"][\"groups\"]\\n"
        "  alerts=json.load(urllib.request.urlopen(alerts_url,timeout=2))[\"data\"][\"alerts\"]\\n"
        "  target=any(t[\"labels\"].get(\"job\")==\"traefik\" and t[\"health\"]==\"up\" and \"127.0.0.1:8082\" in t[\"scrapeUrl\"] for t in targets)\\n"
        "  rule=any(\"5..\" in alert.get(\"query\",\"\") and alert.get(\"type\")==\"alerting\" for group in groups for alert in group[\"rules\"])\\n"
        "  firing=any(alert[\"state\"]==\"firing\" for alert in alerts)\\n"
        "  ready=target and rule and firing\\n"
        "  if ready: break\\n"
        " except Exception:\\n"
        "  pass\\n"
        " time.sleep(1)\\n"
        "print(\"ok\" if status==503 and ready else \"invalid\")\\n"
        "\"\"\")'"
    )
    assert (
        _dans_le_delai(edge)
        and result.rc == 0
        and result.stdout.strip() == "ok"
    ), message(
        en="Prometheus must report the loopback Traefik target up, load a 5xx "
        "alerting rule, and show it firing after the real HTTP 503.",
        fr="Prometheus doit déclarer active la cible Traefik locale, charger "
        "une règle d'alerte 5xx et la déclencher après le véritable HTTP 503.",
    )
