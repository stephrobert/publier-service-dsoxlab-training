# Scenario

An order API runs on `edge.lab`. A client team reports two kinds of trouble:
some orders created through a redirect arrive as the wrong kind of request, and
after a network cut the same order appears twice. You are asked to run the
acceptance test of the API before the client goes live.

## Mission

Read `/home/student/README-api`, send the recette request it describes, record
what each redirect does to a POST and what each error route returns in
`/home/student/recette-http.yaml`, and write `/home/student/envoyer-commande.sh`,
a client that sends an order and never creates it twice, even when the response
is lost.
