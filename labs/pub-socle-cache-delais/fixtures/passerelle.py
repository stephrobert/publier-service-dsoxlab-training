#!/usr/bin/env python3
"""La passerelle parametrable du lab pub-socle-cache-delais.

Elle met en cache, elle rejoue, elle borne les delais, et elle fait tout cela
EXACTEMENT comme `politique-cache.yaml` le dit. Elle n'a aucune valeur par
defaut prudente : la politique livree est rapide et dangereuse, et la
passerelle l'applique fidelement.

QUATRE CLES, ET DEUX PIEGES

  cache.cacher          les prefixes dont la reponse est reutilisable
  cache.varier_sur      les en-tetes qui distinguent deux reponses cachees
  tentatives.rejouer    les METHODES qu'on a le droit de rejouer
  delais.lecture        au bout de combien de secondes on abandonne

Premier piege : `varier_sur`. Cacher `/public` sans varier sur la langue sert
la version francaise a qui demande l'anglais. Cacher une route privee sans
varier sur l'identite sert les donnees d'Alice a Bob, et c'est la fuite que
ce lab existe pour empecher.

Second piege : `rejouer`. Rejouer un POST dont la reponse s'est perdue double
l'action. Le client ne voit aucune difference entre « l'action n'a pas eu
lieu » et « l'action a eu lieu mais la reponse s'est perdue » : seul le
serveur le sait, et c'est pourquoi la decision se prend sur la METHODE, pas
sur ce qu'on observe.
"""

from __future__ import annotations

import http.client
import http.server
import pathlib
import socket
import time
import urllib.error
import urllib.request

import yaml

POLITIQUE = pathlib.Path("/opt/pub-socle-cache-delais/politique-cache.yaml")
AMONT = "http://127.0.0.1:18091"

# cle -> (instant, corps). Volontairement en memoire : un cache qui survit au
# redemarrage masquerait les essais de l'apprenant.
_CACHE: dict[tuple, tuple[float, bytes]] = {}


def _politique() -> dict:
    """Relue a chaque requete, pour que la modification se voie aussitot."""
    if not POLITIQUE.is_file():
        return {}
    try:
        charge = yaml.safe_load(POLITIQUE.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return charge if isinstance(charge, dict) else {}


def _liste(noeud, *chemin) -> list[str]:
    for cle in chemin:
        if not isinstance(noeud, dict):
            return []
        noeud = noeud.get(cle)
    if isinstance(noeud, str):
        return [noeud]
    return [str(e) for e in (noeud or [])]


class Passerelle(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        politique = _politique()
        cachable = any(self.path.startswith(p)
                       for p in _liste(politique, "cache", "cacher"))
        cle = self._cle(politique) if cachable else None

        if cle is not None and cle in _CACHE:
            _, corps = _CACHE[cle]
            self._envoyer(200, corps, cache="HIT")
            return

        try:
            corps, statut = self._amont("GET", politique)
        except (urllib.error.URLError, socket.timeout, TimeoutError) as erreur:
            self._envoyer(504, f"delai depasse : {erreur}\n".encode())
            return

        if cle is not None and statut == 200:
            _CACHE[cle] = (time.time(), corps)
        self._envoyer(statut, corps, cache="MISS" if cachable else "")

    def do_POST(self):  # noqa: N802
        politique = _politique()
        rejouables = [m.upper() for m in _liste(politique, "tentatives", "rejouer")]
        essais = 2 if "POST" in rejouables else 1

        dernier = b""
        for _ in range(essais):
            try:
                dernier, statut = self._amont("POST", politique)
                self._envoyer(statut, dernier)
                return
            except (urllib.error.URLError, socket.timeout, TimeoutError,
                    http.client.RemoteDisconnected) as erreur:
                dernier = f"amont coupe : {erreur}\n".encode()
        self._envoyer(502, dernier)

    def _cle(self, politique: dict) -> tuple:
        """La cle de cache : le chemin, plus les en-tetes declares dans `varier_sur`.

        Un en-tete absent de cette liste ne distingue RIEN : deux requetes qui
        ne different que par lui partagent la meme entree de cache. C'est
        tout le sujet du lab.
        """
        varier = [h.lower() for h in _liste(politique, "cache", "varier_sur")]
        return (self.path, *(self.headers.get(h, "") for h in sorted(varier)))

    def _amont(self, methode: str, politique: dict) -> tuple[bytes, int]:
        delai = politique.get("delais") or {}
        lecture = float(delai.get("lecture", 30)) if isinstance(delai, dict) else 30.0
        requete = urllib.request.Request(AMONT + self.path, method=methode)
        for nom in ("Authorization", "Accept-Language"):
            if self.headers.get(nom):
                requete.add_header(nom, self.headers[nom])
        with urllib.request.urlopen(requete, timeout=lecture) as rep:
            return rep.read(), rep.status

    def _envoyer(self, statut: int, corps: bytes, cache: str = "") -> None:
        self.send_response(statut)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        if cache:
            self.send_header("X-Cache", cache)
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):
        return


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", 80), Passerelle).serve_forever()  # noqa: S104
