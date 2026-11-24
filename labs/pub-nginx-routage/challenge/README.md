# Scenario

An Nginx configuration publishes an application and an administration page.
It works, and it overlaps: a prefix captures what a regular expression was
meant to handle, a redirect loops, and above all **no server is declared as
the default**, so every unknown host name lands on the first block in the
file, the administration one.

The expected selection matrix is in `/opt/pub-nginx-routage/matrice.txt`.

## Mission

Repair the selection so every URL reaches its handler, close the door on the
unknown host name, fix the redirect, and **write down your reading of the
selection rule** in `/home/student/selection.yaml`.

## Why a prediction is asked for, and not an explanation

A machine cannot judge an explanation. Grading it on length and vocabulary
would let incoherent text through, as this catalog has found elsewhere.

You are therefore asked to **predict** where each URL of the matrix lands,
and the validation compares your prediction with what the server actually
does. Predicting correctly on a wrong configuration does not pass;
configuring correctly without being able to predict it does not either. It
is the same requirement, made measurable.

## What is checked

- every URL of the matrix reaches its intended handler. The backend echoes
  the name of the handler that called it: what is measured is what is
  **chosen**, not what is written;
- **critical**: an unknown name serves neither the application nor the
  administration, and gets a refusal;
- `/ancien` redirects to `/nouveau` keeping the authority, without looping.
  The test counts the hops;
- your predictions match the real behaviour.

## Hints

- Nginx prefers a regular expression over a plain prefix, **unless** that
  prefix carries `^~`. And an exact `=` match wins over everything.
- A default server is declared with `default_server` on its `listen`. The
  one that serves nothing is often the best.
- A redirect targeting the prefix it is declared on loops. The test follows
  up to five hops then gives up.
