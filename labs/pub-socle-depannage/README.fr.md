# pub-socle-depannage

**Public :** l'apprenant.

Un incident de production n'annonce jamais sa couche. Ce lab vous confie un
service publié, `depan.test` sur `edge.lab`, portant exactement une panne
tirée au sort parmi DNS, transport, TLS, la route et le backend, et un bruit
de fond sans rapport avec elle.

## Ce que vous saurez faire

- Formuler une hypothèse à partir de l'observation, puis la confirmer ou la
  réfuter par un test ciblé, en gardant un journal horodaté de ce que vous
  avez essayé et constaté.
- Nommer la couche et le composant réellement fautifs, à distinguer d'une
  supposition plausible mais fausse et du bruit sans rapport dans les
  journaux.
- Réparer la panne par une correction minimale et ciblée, et prouver que les
  routes saines fonctionnent encore ensuite, y compris face à une nouvelle
  salve de tests.
- Prouver qu'aucune protection n'a été retirée pour faire répondre à nouveau
  le service : la route interdite reste interdite, le backend reste
  injoignable directement, et TLS reste obligatoire.
