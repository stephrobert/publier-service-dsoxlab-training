"""Quatre rôles pour le lab pub-socle-observabilite, tous sur edge.lab.

ROLE=metier        route d'affaires /commande (échoue si le drapeau de panne
                   existe) et route de santé /sante (toujours saine, jamais
                   une route d'affaires) ; journalise chaque requête en JSON.
ROLE=generateur    trafic client synthétique continu vers /commande ; peut
                   être arrêté (systemctl stop) pour simuler une absence de
                   trafic réelle, sans toucher à metier ni à l'exportateur.
ROLE=exportateur   relit le journal et publie des compteurs agrégés sur une
                   fenêtre glissante fixe, plus un horodatage d'export. Geler
                   ce process (SIGSTOP) simule une collecte qui ne progresse
                   plus sans couper le réseau.
ROLE=evaluateur     relit la politique (réglages de l'apprenant) à chaque
                   tour, interroge l'exportateur, et distingue panne réelle,
                   absence de trafic et collecte perdue. Expose /diagnostic.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROLE = os.environ["ROLE"]
BIND = "127.0.0.1"

ACCES_LOG = os.environ.get("ACCES_LOG", "/var/log/pub-obs/acces.log")
PANNE_FLAG = os.environ.get("PANNE_FLAG", "/var/lib/pub-obs/panne")
POLITIQUE = os.environ.get("POLITIQUE", "/etc/pub-obs/politique.yaml")
FENETRE_S = float(os.environ.get("FENETRE_S", "10"))


def _repondre(gestionnaire: BaseHTTPRequestHandler, code: int, corps: bytes) -> None:
    gestionnaire.send_response(code)
    gestionnaire.send_header("Content-Type", "application/json")
    gestionnaire.send_header("Content-Length", str(len(corps)))
    gestionnaire.end_headers()
    gestionnaire.wfile.write(corps)


# -- ROLE=metier ----------------------------------------------------------


class GestionnaireMetier(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def do_GET(self):
        debut = time.perf_counter()
        requete_id = self.headers.get("X-Request-Id") or os.urandom(4).hex()
        lot = self.headers.get("X-Batch-Id", "generateur")
        force_code = self.headers.get("X-Force-Code")
        force_latence = self.headers.get("X-Force-Latency-Ms")

        if self.path.startswith("/sante"):
            route = "/sante"
            time.sleep(0.005)
            code = 200
        else:
            route = "/commande"
            if force_latence is not None:
                time.sleep(int(force_latence) / 1000)
            else:
                time.sleep(0.02 if not os.path.exists(PANNE_FLAG) else 0.08)
            if force_code is not None:
                code = int(force_code)
            elif os.path.exists(PANNE_FLAG):
                code = 500
            else:
                code = 200

        latence_ms = round((time.perf_counter() - debut) * 1000)
        ligne = {
            "ts": time.time(),
            "id": requete_id,
            "route": route,
            "code": code,
            "latence_ms": latence_ms,
            "lot": lot,
        }
        with open(ACCES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne) + "\n")
        _repondre(self, code, json.dumps({"id": requete_id, "code": code}).encode())


# -- ROLE=generateur --------------------------------------------------------


def _generer() -> None:
    port = int(os.environ["PORT_METIER"])
    intervalle = float(os.environ.get("INTERVALLE_S", "0.3"))
    while True:
        requete_id = os.urandom(4).hex()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/commande", headers={"X-Request-Id": requete_id}
            )
            urllib.request.urlopen(req, timeout=2).read()
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(intervalle)


# -- ROLE=exportateur ---------------------------------------------------------


_COMPTEURS = {"total": 0, "succes": 0, "recent_total": 0, "recent_succes": 0, "export_ts": 0.0}
_VERROU = threading.Lock()


def _relire_journal() -> None:
    maintenant = time.time()
    total = succes = recent_total = recent_succes = 0
    try:
        with open(ACCES_LOG, encoding="utf-8") as f:
            for ligne in f:
                try:
                    evt = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                if evt.get("route") != "/commande":
                    continue
                total += 1
                ok = 200 <= evt.get("code", 0) < 300
                if ok:
                    succes += 1
                if maintenant - evt.get("ts", 0) <= FENETRE_S:
                    recent_total += 1
                    if ok:
                        recent_succes += 1
    except FileNotFoundError:
        pass
    with _VERROU:
        _COMPTEURS.update(
            total=total,
            succes=succes,
            recent_total=recent_total,
            recent_succes=recent_succes,
            export_ts=maintenant,
        )


def _boucle_exportateur() -> None:
    while True:
        _relire_journal()
        time.sleep(2)


class GestionnaireExportateur(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def do_GET(self):
        with _VERROU:
            c = dict(_COMPTEURS)
        corps = (
            f"pub_obs_requests_total {c['total']}\n"
            f"pub_obs_requests_success_total {c['succes']}\n"
            f"pub_obs_requests_recent_total {c['recent_total']}\n"
            f"pub_obs_requests_recent_success_total {c['recent_succes']}\n"
            f"pub_obs_export_timestamp {c['export_ts']}\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


# -- ROLE=evaluateur ---------------------------------------------------------


def _charger_politique() -> dict:
    import yaml

    try:
        with open(POLITIQUE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


_CACHE = {"recent_total": 0, "recent_succes": 0, "export_ts": 0.0}


def _interroger_exportateur() -> None:
    port = os.environ["PORT_EXPORTATEUR"]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2) as rep:
            brut = rep.read().decode()
    except (urllib.error.URLError, OSError, TimeoutError):
        return
    valeurs = {m.group(1): float(m.group(2)) for m in re.finditer(r"(\w+) ([\d.]+)", brut)}
    _CACHE["recent_total"] = int(valeurs.get("pub_obs_requests_recent_total", 0))
    _CACHE["recent_succes"] = int(valeurs.get("pub_obs_requests_recent_success_total", 0))
    _CACHE["export_ts"] = valeurs.get("pub_obs_export_timestamp", _CACHE["export_ts"])


def _diagnostiquer() -> dict:
    politique = _charger_politique()
    collecte = politique.get("collecte") or {}
    trafic = politique.get("trafic") or {}
    alerte = politique.get("alerte") or {}
    staleness_max = float(collecte.get("staleness_max_s", 600))
    seuil_minimum = int(trafic.get("seuil_minimum", 500))
    seuil_erreur = float(alerte.get("seuil_taux_erreur", 1.1))

    age = time.time() - _CACHE["export_ts"] if _CACHE["export_ts"] else 10**9
    total = _CACHE["recent_total"]
    succes = _CACHE["recent_succes"]

    if age > staleness_max:
        return {"classification": "collecte_perdue", "firing": False, "age_collecte_s": round(age, 1)}
    if total < seuil_minimum:
        return {"classification": "absence_trafic", "firing": False, "total_fenetre": total}
    taux_erreur = 1 - (succes / total)
    if taux_erreur >= seuil_erreur:
        return {
            "classification": "panne_reelle",
            "firing": True,
            "taux_erreur": round(taux_erreur, 3),
            "total_fenetre": total,
        }
    return {
        "classification": "nominal",
        "firing": False,
        "taux_erreur": round(taux_erreur, 3),
        "total_fenetre": total,
    }


def _boucle_evaluateur() -> None:
    while True:
        _interroger_exportateur()
        time.sleep(1)


class GestionnaireEvaluateur(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith("/diagnostic"):
            corps = json.dumps(_diagnostiquer()).encode()
            _repondre(self, 200, corps)
        else:
            _repondre(self, 404, b"{}")


def principal() -> None:
    if ROLE == "metier":
        ThreadingHTTPServer((BIND, int(os.environ["PORT"])), GestionnaireMetier).serve_forever()
    elif ROLE == "generateur":
        _generer()
    elif ROLE == "exportateur":
        threading.Thread(target=_boucle_exportateur, daemon=True).start()
        ThreadingHTTPServer((BIND, int(os.environ["PORT"])), GestionnaireExportateur).serve_forever()
    elif ROLE == "evaluateur":
        threading.Thread(target=_boucle_evaluateur, daemon=True).start()
        ThreadingHTTPServer((BIND, int(os.environ["PORT"])), GestionnaireEvaluateur).serve_forever()
    else:
        raise SystemExit(f"ROLE inconnu: {ROLE}")


if __name__ == "__main__":
    principal()
