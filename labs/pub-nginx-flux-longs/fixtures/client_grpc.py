#!/usr/bin/env python3
"""Un client gRPC generique, pose sur le client du lab.

Il appelle /essai.Echo/Dire a travers Nginx et IMPRIME ce qu'il observe :
  ok <reponse>           l'appel a abouti
  erreur <code> <detail> le serveur a refuse, et c'est une erreur APPLICATIVE
  transport <message>    l'appel n'a meme pas abouti au serveur

La distinction entre les deux dernieres lignes est tout le propos du
troisieme controle : un proxy mal regle transforme un refus applicatif en
panne de transport, et le client ne sait plus quoi reessayer.
"""

from __future__ import annotations

import sys

import grpc

CIBLE = sys.argv[1]
CHARGE = sys.argv[2].encode()

try:
    canal = grpc.insecure_channel(CIBLE)
    appel = canal.unary_unary(
        "/essai.Echo/Dire",
        request_serializer=lambda o: o,
        response_deserializer=lambda o: o,
    )
    reponse = appel(CHARGE, timeout=10)
    print("ok", reponse.decode("utf-8", "replace"))
except grpc.RpcError as erreur:
    code = erreur.code()
    if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
        print("transport", code.name, erreur.details())
    else:
        print("erreur", code.name, erreur.details())
