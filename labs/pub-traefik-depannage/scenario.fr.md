# Scénario

Plusieurs services derrière Traefik sont devenus instables. Les utilisateurs
signalent des pages absentes, des erreurs de passerelle, des requêtes lentes,
un avertissement de certificat et des redirections qui ne finissent jamais.

## Mission

Servez-vous des journaux du proxy et des accès pour localiser chaque panne,
réparez la configuration dynamique et vérifiez les réponses réelles. Traefik
doit rester actif pendant le rechargement du fournisseur fichier.
