# The task

Fix `/opt/pub-routage/dynamic/routes.yaml`. The default router must only win
when no more specific rule applies: raise `api-v2`'s priority above
`api-v1-defaut`'s, or lower the default's, so that `routage.lab.test/v2*`
reaches `api-v2` while the root still reaches `api-v1`. Scope the admin
router to `Host(`routage.lab.test`) && PathPrefix(`/admin`)` so no other
hostname reaches it. Qualify the catalog router's service and middleware to
the Docker provider (`cible@docker`, `marque@docker`). The checks call the
real HTTP entrypoint on port 80, read the response body (`Hostname:`) and
headers, and add one more unrelated dynamic route to prove nothing breaks.
