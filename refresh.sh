#!/bin/bash
# Relève le barème carburant UPS et le publie sur GitHub.
# Lancé chaque semaine par launchd (voir com.t26.upsfuel.plist).
#
# UPS refuse les IP de datacenter : GitHub Actions se fait couper la connexion
# (ERR_HTTP2_PROTOCOL_ERROR), alors qu'une connexion ordinaire passe. La relève
# se fait donc depuis ce poste, et seul le résultat est publié.
set -uo pipefail
cd "$(dirname "$0")" || exit 1

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

if ! python3 scrape_local.py; then
  echo "Relève échouée — ups-fuel.json inchangé, rien n'est publié."
  exit 1
fi

if [ -z "$(git status --porcelain ups-fuel.json)" ]; then
  echo "Barème inchangé — rien à publier."
  exit 0
fi

DATE=$(python3 -c "import json;print(json.load(open('ups-fuel.json'))['effective_date'])")
git add ups-fuel.json
git commit -q -m "Barème carburant UPS du $DATE"
if git push -q; then
  echo "Publié : barème du $DATE."
else
  echo "Publication impossible (réseau ou identifiants) — le commit local est conservé."
  exit 1
fi
