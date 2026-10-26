#!/usr/bin/env bash
# Chiffre solution-en-clair/<lab>/solution.yaml vers solution/<lab>/solution.yaml
# avec ansible-vault et le mot de passe du dépôt, qui n'est jamais versionné.
#
# POURQUOI CE SCRIPT EXISTE
#
# Les corrigés de ce catalogue n'existaient que chiffrés. Les relire demandait
# un `ansible-vault view` à la main, et les modifier un aller-retour que rien
# ne guidait : les catalogues frères ont tous ce script, et il manquait ici.
#
# UNE SOLUTION DONT LE CLAIR N'A PAS CHANGÉ N'EST PAS RECHIFFRÉE
#
# Le chiffré change à chaque passage, puisque le sel est tiré au hasard. Le
# recalculer sans raison ferait apparaître le fichier comme modifié, et le
# garde-fou `verdicts-et-commun-separes` en conclurait que l'attestation du
# lab est périmée. Un outil qui invente du changement fait mentir les
# contrôles bâtis autour de lui.
set -euo pipefail
cd "$(dirname "$0")/.."

PASSE=.vault-pass
[ -s "$PASSE" ] || { echo "$PASSE absent : impossible de chiffrer." >&2; exit 1; }

# Le contrôle qui compte, joué AVANT d'écrire quoi que ce soit : sur un dépôt
# public, oublier une fois suffit.
if ! git check-ignore -q "$PASSE"; then
  echo "ECHEC : git n'ignore pas « $PASSE ». Rien n'a été chiffré." >&2
  exit 1
fi

if [ ! -d solution-en-clair ]; then
  echo "Aucun solution-en-clair/ : rien à chiffrer."
  echo "Pour reprendre un corrigé existant :"
  echo "  mkdir -p solution-en-clair/<lab>"
  echo "  ansible-vault view --vault-password-file $PASSE \\"
  echo "    solution/<lab>/solution.yaml > solution-en-clair/<lab>/solution.yaml"
  exit 0
fi

inchanges=0
chiffres=0
while IFS= read -r clair; do
  cible="solution/${clair#solution-en-clair/}"
  mkdir -p "$(dirname "$cible")"
  if [ -s "$cible" ] && ansible-vault view --vault-password-file "$PASSE" \
       "$cible" </dev/null 2>/dev/null | cmp -s - "$clair"; then
    inchanges=$((inchanges + 1))
    continue
  fi
  ansible-vault encrypt --vault-password-file "$PASSE" \
    --output "$cible" "$clair" </dev/null >/dev/null 2>&1
  # Chiffrer sans relire, c'est publier un fichier dont personne ne sait s'il
  # porte ce qu'on croit.
  if ! ansible-vault view --vault-password-file "$PASSE" "$cible" </dev/null \
       2>/dev/null | cmp -s - "$clair"; then
    echo "ECHEC : $cible ne redonne pas son clair." >&2
    exit 1
  fi
  echo "chiffré : $cible"
  chiffres=$((chiffres + 1))
done < <(find solution-en-clair -name solution.yaml | sort)

echo "$chiffres chiffré(s), $inchanges inchangé(s)."
