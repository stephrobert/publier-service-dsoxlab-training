# Scenario

A single-page application, its assets, a private file and an API are
published by a configuration that serves all of it **without distinction**:
no correct MIME type, a fallback that swallows every error, private files
reachable, and `0777` permissions.

What the publication must present is written in
`/opt/pub-nginx-statique/attendu.txt`.

## Mission

Publish the intended resources with their type, keep real errors, refuse
what is private, and tighten the permissions without ceasing to serve.

## The costliest defect is the one you cannot see

A `try_files $uri $uri/ /index.html` placed on the root turns **every**
error into a success. A missing asset answers 200 with HTML, and so does an
unknown API call. The page renders, everything looks fine, and the defect is
diagnosed three weeks later, when someone notices a `fetch` receiving HTML
instead of its JSON.

The fallback is nevertheless **legitimate** for the application's routes:
`/accueil` must indeed return `index.html`. The validation therefore
requires both, and that is what separates a correct publication from one
that merely works.

## What is checked

- the intended resources carry the right body **and** the right MIME type. A
  JavaScript served as `application/octet-stream` is downloaded instead of
  executed;
- the fallback serves the application's routes and **only** those:
  `/assets/absent.js` stays a 404, and the API answers for itself;
- **critical**: the private file, dotfiles and path traversals are refused.
  The test looks for the **secret in the body**, not for a status code: a
  200 returning `index.html` on `/.env` is not a leak, a 200 returning the
  key is;
- **critical**: no file is world-readable any more, and the assets are still
  served. Removing every permission would protect perfectly and serve
  nothing.

## Hints

- `include mime.types;` loads the distribution's type table. Without it,
  `default_type` applies to everything.
- A `try_files` placed inside a `location` applies to that one only.
- Workers run as `www-data`: read access is given through ownership or
  group, never by opening to all.
