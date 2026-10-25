# Scenario

A catalogue application runs on `edge.lab`. Its home page loads, its health
check says `ok`, and yet the list of books returns an error. Nobody can tell
you which process answers, under which user, on which port, or what it depends
on. You are taking over the service.

## Mission

Write the service sheet of the application in `/home/student/fiche-service.yaml`
and bring the business function back, then prove what a restart does to the
application's state. Start from what the system reports, not from what you
assume.
